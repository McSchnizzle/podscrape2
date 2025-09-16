#!/usr/bin/env python3
"""
Audio Processing Phase Script - Download and Transcription
Independent script for Phase 2: Download audio, chunk, and transcribe episodes
Reads JSON input from discovery phase or direct episode data.
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
import argparse

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

# Set up environment
from dotenv import load_dotenv
load_dotenv()
from src.config.env import require_database_url
require_database_url()

from src.database.models import get_episode_repo, Episode
from src.podcast.audio_processor import AudioProcessor
from src.utils.logging_config import setup_phase_logging

class AudioProcessor_Runner:
    """Audio download and transcription phase"""

    def __init__(self, dry_run: bool = False, limit: int = None, verbose: bool = False):
        # Set up phase-specific logging
        self.pipeline_logger = setup_phase_logging("audio", verbose=verbose, console_output=True)
        self.logger = self.pipeline_logger.get_logger()

        self.dry_run = dry_run
        self.limit = limit
        self.verbose = verbose

        # Initialize repositories and components - with explicit cleanup tracking
        self.episode_repo = get_episode_repo()
        self._db_connections = [self.episode_repo]  # Track for cleanup

        # Verify dependencies
        self._verify_dependencies()

        # Initialize Web UI config for audio settings - minimize database usage
        chunk_minutes = 3
        try:
            from src.config.web_config import WebConfigManager
            # Use a single config lookup and close immediately
            web_config = WebConfigManager()
            try:
                chunk_minutes = int(web_config.get_setting('audio_processing', 'chunk_duration_minutes', 3))
            except Exception:
                pass
            # Explicitly cleanup web config connection
            try:
                web_config.close()
            except (AttributeError, Exception):
                pass
            del web_config  # Explicit cleanup
        except Exception:
            pass

        self.audio_processor = AudioProcessor(chunk_duration_minutes=chunk_minutes)

        # Initialize OpenAI Whisper transcriber
        self.transcriber = None
        if self.has_openai_whisper:
            from src.podcast.openai_whisper_transcriber import create_openai_whisper_transcriber
            self.transcriber = create_openai_whisper_transcriber(chunk_duration_minutes=chunk_minutes)

        self.pipeline_logger.log_phase_start("Audio download and transcription processing")

    def _verify_dependencies(self):
        """Verify required dependencies"""
        self.logger.info("Verifying dependencies...")

        # Check OpenAI Whisper
        try:
            import whisper
            import torch
            from src.podcast.openai_whisper_transcriber import create_openai_whisper_transcriber
            self.logger.info("✓ OpenAI Whisper available")
            self.has_openai_whisper = True
        except ImportError as e:
            self.logger.warning("✗ OpenAI Whisper not available")
            self.logger.warning(f"Error: {e}")
            self.has_openai_whisper = False

        # Check FFmpeg
        try:
            import subprocess
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
            self.logger.info("✓ FFmpeg available")
        except FileNotFoundError:
            self.logger.error("✗ FFmpeg not found - required for audio processing")
            raise Exception("FFmpeg not available")

        self.logger.info("✅ Dependencies verified")

    def cleanup(self):
        """Cleanup database connections and resources"""
        try:
            for connection in getattr(self, '_db_connections', []):
                try:
                    if hasattr(connection, 'close'):
                        connection.close()
                except Exception:
                    pass
            self._db_connections = []
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def process_episodes(self, episodes_data):
        """Process audio for episodes from discovery phase or direct input"""

        if isinstance(episodes_data, str):
            # Load from JSON file
            with open(episodes_data, 'r') as f:
                data = json.load(f)
            if not data.get('success', False):
                return {
                    'success': False,
                    'error': f"Discovery phase failed: {data.get('error', 'Unknown error')}",
                    'episodes_processed': 0,
                    'episodes': []
                }
            episodes = data.get('episodes', [])
        elif isinstance(episodes_data, dict):
            # Direct JSON data
            if not episodes_data.get('success', False):
                return {
                    'success': False,
                    'error': f"Discovery phase failed: {episodes_data.get('error', 'Unknown error')}",
                    'episodes_processed': 0,
                    'episodes': []
                }
            episodes = episodes_data.get('episodes', [])
        else:
            return {
                'success': False,
                'error': "Invalid input format - expected JSON file path or dict",
                'episodes_processed': 0,
                'episodes': []
            }

        if not episodes:
            return {
                'success': True,
                'episodes_processed': 0,
                'episodes': [],
                'message': "No episodes to process"
            }

        # Apply limit
        if self.limit:
            episodes = episodes[:self.limit]

        self.logger.info(f"Processing {len(episodes)} episodes")

        processed_episodes = []
        failed_episodes = []

        for i, episode_data in enumerate(episodes, 1):
            try:
                self.logger.info(f"\n[{i}/{len(episodes)}] Processing: {episode_data['title']}")

                if self.dry_run:
                    self.logger.info("🔍 DRY RUN: Would process audio")
                    processed_episodes.append({
                        'guid': episode_data['guid'],
                        'title': episode_data['title'],
                        'status': 'dry_run',
                        'transcript_path': None,
                        'transcript_words': 0
                    })
                    continue

                # Process the episode
                result = self._process_episode_audio(episode_data)
                if result['success']:
                    processed_episodes.append(result)
                else:
                    failed_episodes.append({
                        'guid': episode_data['guid'],
                        'title': episode_data['title'],
                        'error': result['error']
                    })

                # Force cleanup after each episode to prevent resource accumulation
                try:
                    import gc
                    gc.collect()  # Force garbage collection
                except Exception:
                    pass

            except Exception as e:
                self.logger.error(f"Failed to process episode {episode_data['title']}: {e}")
                failed_episodes.append({
                    'guid': episode_data['guid'],
                    'title': episode_data['title'],
                    'error': str(e)
                })

        return {
            'success': len(failed_episodes) == 0,
            'episodes_processed': len(processed_episodes),
            'episodes_failed': len(failed_episodes),
            'episodes': processed_episodes,
            'failed': failed_episodes
        }

    def _process_episode_audio(self, episode_data):
        """Process audio for a single episode"""

        episode_guid = episode_data['guid']

        # Handle both new episodes and resume cases
        if episode_data.get('mode') == 'resume':
            # Resume existing episode
            db_episode = self.episode_repo.get_by_episode_guid(episode_guid)
            if not db_episode:
                return {
                    'success': False,
                    'error': f"Episode {episode_guid} not found in database for resume"
                }
        else:
            # Check if episode already exists
            existing = self.episode_repo.get_by_episode_guid(episode_guid)
            if existing:
                db_episode = existing
                self.logger.info(f"Resuming existing episode: {existing.status}")
            else:
                # Create new episode record
                db_episode = Episode(
                    episode_guid=episode_guid,
                    feed_id=episode_data.get('feed_id') or 1,
                    title=episode_data['title'],
                    published_date=datetime.fromisoformat(episode_data['published_date'].replace('Z', '+00:00')),
                    audio_url=episode_data['audio_url'],
                    duration_seconds=episode_data.get('duration_seconds'),
                    description=episode_data.get('description', '')
                )
                episode_id = self.episode_repo.create(db_episode)
                db_episode.id = episode_id
                self.logger.info(f"✓ Database record created (ID: {episode_id})")

        try:
            # Step 1: Download audio
            self.logger.info("Downloading audio...")
            audio_path = self.audio_processor.download_audio(db_episode.audio_url, episode_guid)
            audio_size_mb = Path(audio_path).stat().st_size / (1024*1024)
            self.logger.info(f"✓ Downloaded {audio_size_mb:.1f}MB")

            # Step 2: Chunk audio
            self.logger.info("Chunking audio...")
            chunk_paths = self.audio_processor.chunk_audio(audio_path, episode_guid)

            # Apply transcription limits
            transcribe_all = True
            max_chunks = None
            try:
                from src.config.web_config import WebConfigManager
                # Use a single config lookup and close immediately
                web_config = WebConfigManager()
                try:
                    transcribe_all = bool(web_config.get_setting('audio_processing', 'transcribe_all_chunks', True))
                    max_chunks = int(web_config.get_setting('audio_processing', 'max_chunks_per_episode', 3))
                except Exception:
                    pass
                # Explicitly cleanup web config connection
                try:
                    web_config.close()
                except (AttributeError, Exception):
                    pass
                del web_config  # Explicit cleanup
            except Exception:
                pass

            if not transcribe_all and isinstance(max_chunks, int) and max_chunks > 0:
                if len(chunk_paths) > max_chunks:
                    self.logger.info(f"⚠️ Limiting to first {max_chunks} chunks (of {len(chunk_paths)})")
                    chunk_paths = chunk_paths[:max_chunks]

            self.logger.info(f"✓ Processing {len(chunk_paths)} chunks")

            # Step 3: Transcription
            if not self.transcriber:
                self.logger.warning("Transcriber not available; skipping transcription")
                return {
                    'success': False,
                    'error': "Transcriber not available"
                }

            self.logger.info("Starting transcription...")
            model_info = self.transcriber.get_model_info()
            self.logger.info(f"Using OpenAI Whisper: {model_info.get('model', 'unknown')} model")

            # Convert paths to strings for Whisper API
            chunk_paths_str = [str(path) for path in chunk_paths]

            # Transcribe
            transcription_result = self.transcriber.transcribe_episode(chunk_paths_str, episode_guid)

            # Combine transcripts
            all_transcripts = [chunk.text for chunk in transcription_result.chunks]
            combined_transcript = "\n\n".join([t for t in all_transcripts if t])
            total_words = len(combined_transcript.split())
            total_chars = len(combined_transcript)

            # Save transcript
            transcript_dir = Path("data/transcripts")
            transcript_dir.mkdir(parents=True, exist_ok=True)

            feed_name = episode_data.get('feed_name', 'Unknown')
            feed_prefix = feed_name.split()[0].lower()
            short_guid = episode_guid[:6]
            transcript_filename = f"{feed_prefix}-{short_guid}.txt"
            transcript_path = transcript_dir / transcript_filename

            with open(transcript_path, 'w', encoding='utf-8') as f:
                f.write(f"# Complete Transcript\n")
                f.write(f"# Episode: {db_episode.title}\n")
                f.write(f"# Feed: {feed_name}\n")
                f.write(f"# GUID: {episode_guid}\n")
                f.write(f"# Processed: {datetime.now().isoformat()}\n")
                f.write(f"# Chunks: {len(chunk_paths)}\n")
                f.write(f"# Words: {total_words:,}\n")
                f.write(f"# Characters: {total_chars:,}\n\n")
                f.write(combined_transcript)

            # Update database
            self.episode_repo.update_transcript(episode_guid, str(transcript_path), total_words)

            # Cleanup audio files
            self._cleanup_audio_files(episode_guid, chunk_paths)

            self.logger.info(f"✅ Transcription complete: {total_words:,} words")

            return {
                'success': True,
                'guid': episode_guid,
                'title': db_episode.title,
                'status': 'transcribed',
                'transcript_path': str(transcript_path),
                'transcript_words': total_words,
                'chunks_processed': len(transcription_result.chunks)
            }

        except Exception as e:
            self.logger.error(f"Audio processing failed: {e}")
            try:
                self.episode_repo.mark_failure(episode_guid, str(e))
            except:
                pass
            return {
                'success': False,
                'error': str(e)
            }

    def _cleanup_audio_files(self, episode_guid, chunk_paths):
        """Clean up temporary audio files"""
        try:
            chunks_deleted = 0
            if chunk_paths:
                chunk_episode_dir = Path(chunk_paths[0]).parent
                if chunk_episode_dir.exists():
                    for chunk_file in chunk_episode_dir.iterdir():
                        if chunk_file.is_file():
                            chunk_file.unlink()
                            chunks_deleted += 1
                    try:
                        chunk_episode_dir.rmdir()
                    except OSError:
                        pass

            # Delete progress file
            progress_file = Path("data/transcripts") / f"{episode_guid}-progress.txt"
            if progress_file.exists():
                progress_file.unlink()

            # Delete original audio file
            episode_id = episode_guid.replace('-', '')[:6]
            audio_cache_dir = Path(self.audio_processor.audio_cache_dir)
            for audio_file in audio_cache_dir.glob(f"*-{episode_id}.mp3"):
                try:
                    audio_file.unlink()
                    break
                except Exception:
                    pass

            self.logger.info(f"✓ Cleanup complete: {chunks_deleted} chunks deleted")

        except Exception as e:
            self.logger.warning(f"⚠️ Cleanup failed: {e}")

def main():
    parser = argparse.ArgumentParser(description='Audio Processing Phase')
    parser.add_argument('input', nargs='?', help='Input JSON file from discovery phase or episode GUID')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be processed')
    parser.add_argument('--limit', type=int, help='Limit number of episodes')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    parser.add_argument('--output', help='Output JSON file (default: stdout)')

    args = parser.parse_args()

    try:
        with AudioProcessor_Runner(
            dry_run=args.dry_run,
            limit=args.limit,
            verbose=args.verbose
        ) as runner:

            # Handle input
            if args.input:
                if args.input.endswith('.json') or '/' in args.input:
                    # JSON file input
                    episodes_data = args.input
                else:
                    # Single episode GUID
                    episodes_data = {
                        'success': True,
                        'episodes': [{
                            'guid': args.input,
                            'title': 'Manual Episode',
                            'mode': 'resume'
                        }]
                    }
            else:
                # Read from stdin
                import sys
                episodes_data = json.load(sys.stdin)

            result = runner.process_episodes(episodes_data)

        # Output JSON
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(result, f, indent=2)
        else:
            print(json.dumps(result))
            sys.stdout.flush()

        # Exit code
        sys.exit(0 if result['success'] else 1)

    except Exception as e:
        error_result = {
            'success': False,
            'error': str(e),
            'episodes_processed': 0,
            'episodes': []
        }

        if args.output:
            with open(args.output, 'w') as f:
                json.dump(error_result, f, indent=2)
        else:
            print(json.dumps(error_result))
            sys.stdout.flush()

        sys.exit(1)

if __name__ == '__main__':
    main()