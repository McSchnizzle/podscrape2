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



def resolve_dry_run_flag(cli_flag: bool) -> bool:
    env_value = os.getenv("DRY_RUN")
    if env_value is not None:
        return env_value.strip().lower() in {"1", "true", "yes", "on"}
    return cli_flag

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
from src.scoring.content_scorer import ContentScorer

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

        # Initialize database configuration reader
        from src.config.web_config import WebConfigReader
        self.config_reader = WebConfigReader()

        # Get settings from database
        self.audio_config = self.config_reader.get_audio_processing_config()
        self.score_threshold = self.config_reader.get_score_threshold()

        # Initialize content scorer for immediate relevance checking
        self.content_scorer = ContentScorer()

        # Verify dependencies
        self._verify_dependencies()

        self.audio_processor = AudioProcessor(chunk_duration_minutes=self.audio_config['chunk_duration_minutes'])

        # Initialize OpenAI Whisper transcriber
        self.transcriber = None
        if self.has_openai_whisper:
            from src.podcast.openai_whisper_transcriber import create_openai_whisper_transcriber
            self.transcriber = create_openai_whisper_transcriber(chunk_duration_minutes=self.audio_config['chunk_duration_minutes'])

        self.logger.info("Audio processing initialized")
        self.logger.info(f"Database settings - Chunk duration: {self.audio_config['chunk_duration_minutes']}min, "
                        f"Max chunks per episode: {self.audio_config['max_chunks_per_episode']}, "
                        f"Transcribe all chunks: {self.audio_config['transcribe_all_chunks']}, "
                        f"STT model: {self.audio_config['stt_model']}")

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

    def process_episodes_optimized(self, max_relevant_episodes):
        """Process episodes until max_relevant_episodes RELEVANT episodes are found.

        This optimization processes episodes from the database (pending status)
        until we accumulate the desired number of RELEVANT episodes (score >= threshold).
        """
        self.logger.info(f"🎯 P2 OPTIMIZATION: Processing until {max_relevant_episodes} relevant episodes found")

        # Get ALL pending episodes (oldest first for chronological processing)
        pending_episodes = self.episode_repo.get_by_status('pending')

        if not pending_episodes:
            return {
                'success': True,
                'episodes_processed': 0,
                'episodes': [],
                'message': "No pending episodes to process"
            }

        self.logger.info(f"📋 Found {len(pending_episodes)} pending episodes to evaluate")

        processed_episodes = []
        failed_episodes = []
        relevant_count = 0
        not_relevant_count = 0
        total_processed = 0

        for episode in pending_episodes:
            total_processed += 1

            self.logger.info(f"\n[{total_processed}] Processing: {episode.title}")

            if self.dry_run:
                self.logger.info("🔍 DRY RUN: Would process and score episode")
                processed_episodes.append({
                    'guid': episode.episode_guid,
                    'title': episode.title,
                    'status': 'dry_run',
                    'transcript_path': None,
                    'transcript_words': 0,
                    'is_relevant': None
                })
                # In dry run, simulate finding relevant episodes
                relevant_count += 1
                if relevant_count >= max_relevant_episodes:
                    self.logger.info(f"🎯 DRY RUN TARGET REACHED: {relevant_count} episodes processed")
                    break
                continue

            try:
                # Step 1: Process audio (download + transcribe)
                episode_data = {
                    'guid': episode.episode_guid,
                    'title': episode.title,
                    'published_date': episode.published_date.isoformat(),
                    'audio_url': episode.audio_url,
                    'duration_seconds': episode.duration_seconds,
                    'description': episode.description or '',
                    'feed_id': episode.feed_id
                }

                audio_result = self._process_episode_audio(episode_data)

                if not audio_result.get('success'):
                    failed_episodes.append({
                        'guid': episode.episode_guid,
                        'title': episode.title,
                        'error': audio_result.get('error', 'Audio processing failed')
                    })
                    continue

                # Step 2: Score the episode immediately after transcription
                scores = self._score_episode_immediately(episode.episode_guid)

                # Step 3: Check relevance against threshold
                is_relevant = any(score >= self.score_threshold for score in scores.values()) if scores else False

                # Update episode status based on relevance
                if is_relevant:
                    relevant_count += 1
                    self.episode_repo.update_status(episode.episode_guid, 'scored')
                    self.logger.info(f"✅ RELEVANT episode ({relevant_count}/{max_relevant_episodes})")

                    processed_episodes.append({
                        **audio_result,
                        'is_relevant': True,
                        'scores': scores
                    })

                    # Check if we've hit our relevant episode limit
                    if relevant_count >= max_relevant_episodes:
                        self.logger.info(f"🎯 TARGET REACHED: {relevant_count} relevant episodes processed")
                        break

                else:
                    not_relevant_count += 1
                    self.episode_repo.update_status(episode.episode_guid, 'not_relevant')
                    self.logger.info(f"❌ Not relevant episode (continuing search...)")

                    # Don't add to processed_episodes - we only return relevant ones

            except Exception as e:
                self.logger.error(f"Failed to process episode {episode.title}: {e}")
                failed_episodes.append({
                    'guid': episode.episode_guid,
                    'title': episode.title,
                    'error': str(e)
                })

        # Enhanced logging summary as requested
        self._log_processing_summary(processed_episodes, relevant_count, not_relevant_count, total_processed)

        return {
            'success': len(failed_episodes) == 0,
            'episodes_processed': len(processed_episodes),  # Only relevant episodes
            'episodes_failed': len(failed_episodes),
            'relevant_episodes_found': relevant_count,
            'not_relevant_episodes_found': not_relevant_count,
            'total_episodes_evaluated': total_processed,
            'episodes': processed_episodes,  # Only relevant episodes
            'failed': failed_episodes,
            'optimization_active': True
        }

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
        if self.limit is not None:
            episodes = episodes[:self.limit]

        self.logger.info(f"Processing {len(episodes)} episodes")

        processed_episodes = []
        failed_episodes = []
        skipped_episodes = []

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
                if result.get('skipped'):
                    skipped_episodes.append(result)
                elif result['success']:
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
            'failed': failed_episodes,
            'skipped': skipped_episodes
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

        # Skip episodes previously marked as not relevant
        if getattr(db_episode, 'status', None) == 'not_relevant':
            self.logger.info("🚫 Skipping episode marked not_relevant (GUID: %s)", episode_guid)
            return {
                'success': True,
                'guid': episode_guid,
                'title': db_episode.title,
                'status': db_episode.status,
                'skipped': True,
                'message': 'Episode previously marked not relevant; skipping audio processing'
            }

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

            # Store transcript in database (no file creation)
            feed_name = episode_data.get('feed_name', 'Unknown')
            feed_prefix = feed_name.split()[0].lower()
            short_guid = episode_guid[:6]
            transcript_filename = f"{feed_prefix}-{short_guid}.txt"

            # Create transcript with metadata header
            transcript_with_metadata = (
                f"# Complete Transcript\n"
                f"# Episode: {db_episode.title}\n"
                f"# Feed: {feed_name}\n"
                f"# GUID: {episode_guid}\n"
                f"# Processed: {datetime.now().isoformat()}\n"
                f"# Chunks: {len(chunk_paths)}\n"
                f"# Words: {total_words:,}\n"
                f"# Characters: {total_chars:,}\n\n"
                f"{combined_transcript}"
            )

            # Update database with transcript content only (no file path)
            self.episode_repo.update_transcript(episode_guid, None, total_words, transcript_with_metadata)

            # Cleanup audio files
            self._cleanup_audio_files(episode_guid, chunk_paths)

            self.logger.info(f"✅ Transcription complete: {total_words:,} words")

            return {
                'success': True,
                'guid': episode_guid,
                'title': db_episode.title,
                'status': 'transcribed',
                'transcript_path': None,  # Stored in database
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

    def _score_episode_immediately(self, episode_guid):
        """Score episode immediately after transcription"""
        try:
            # Get the episode from database
            db_episode = self.episode_repo.get_by_episode_guid(episode_guid)
            if not db_episode or not db_episode.transcript_content:
                self.logger.warning(f"No transcript available for immediate scoring: {episode_guid}")
                return {}

            self.logger.info("⚡ Immediate scoring...")

            # Use the content scorer to get scores
            scoring_result = self.content_scorer.score_transcript(
                db_episode.transcript_content,
                episode_guid
            )

            if scoring_result.success:
                # Store scores in database
                self.episode_repo.update_scores(episode_guid, scoring_result.scores)

                self.logger.info(f"✓ Scores: {', '.join([f'{topic}: {score:.2f}' for topic, score in scoring_result.scores.items()])}")
                return scoring_result.scores
            else:
                self.logger.error(f"Scoring failed: {scoring_result.error_message}")
                return {}

        except Exception as e:
            self.logger.error(f"Immediate scoring failed: {e}")
            return {}

    def _log_processing_summary(self, processed_episodes, relevant_count, not_relevant_count, total_processed):
        """Log comprehensive processing summary as requested"""
        self.logger.info(f"\n📊 AUDIO PHASE PROCESSING SUMMARY:")
        self.logger.info(f"   🎯 Relevant episodes processed: {relevant_count}")
        self.logger.info(f"   🚫 Not relevant episodes processed: {not_relevant_count}")
        self.logger.info(f"   📋 Total episodes evaluated: {total_processed}")
        self.logger.info(f"   ⚡ Optimization: P2 Task #0 (process until relevant count reached)")

        if processed_episodes:
            self.logger.info(f"   📝 Episode Details:")
            for ep in processed_episodes:
                scores_str = ""
                if ep.get('scores'):
                    scores_str = f" - Scores: {', '.join([f'{topic}: {score:.2f}' for topic, score in ep['scores'].items()])}"
                self.logger.info(f"      ✅ {ep['title'][:50]}{'...' if len(ep['title']) > 50 else ''}{scores_str}")

        self.logger.info(f"   🔧 P2 Optimization Benefits:")
        self.logger.info(f"      • Always gets full quota of relevant episodes")
        self.logger.info(f"      • Doesn't waste processing on not_relevant episodes")
        self.logger.info(f"      • Improves content quality in final digest")

def main():
    parser = argparse.ArgumentParser(description='Audio Processing Phase')
    parser.add_argument('input', nargs='?', help='Input JSON file from discovery phase or episode GUID')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be processed')
    parser.add_argument('--limit', type=int, help='Limit number of episodes')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    parser.add_argument('--output', help='Output JSON file (default: stdout)')
    parser.add_argument('--use-optimization', action='store_true', default=True,
                        help='Use P2 optimization (process until relevant episodes found)')
    parser.add_argument('--no-optimization', dest='use_optimization', action='store_false',
                        help='Disable P2 optimization (legacy behavior)')

    args = parser.parse_args()

    dry_run = resolve_dry_run_flag(args.dry_run)

    try:
        with AudioProcessor_Runner(
            dry_run=dry_run,
            limit=args.limit,
            verbose=args.verbose
        ) as runner:

            # Handle input and optimization logic
            if args.input:
                if args.input.endswith('.json') or '/' in args.input:
                    # JSON file input - use traditional processing
                    episodes_data = args.input
                    result = runner.process_episodes(episodes_data)
                else:
                    # Single episode GUID - use traditional processing
                    episodes_data = {
                        'success': True,
                        'episodes': [{
                            'guid': args.input,
                            'title': 'Manual Episode',
                            'mode': 'resume'
                        }]
                    }
                    result = runner.process_episodes(episodes_data)
            else:
                # No input provided - check for stdin or use optimization
                stdin_data = None
                if not sys.stdin.isatty():
                    # Try to read from stdin (traditional orchestrator call)
                    try:
                        stdin_content = sys.stdin.read().strip()
                        if stdin_content:
                            stdin_data = json.loads(stdin_content)
                    except (json.JSONDecodeError, Exception):
                        pass  # Fall through to optimization

                if stdin_data:
                    # Use traditional processing with stdin data
                    result = runner.process_episodes(stdin_data)
                else:
                    # Called directly without input or empty stdin - use optimization
                    if args.use_optimization:
                        max_episodes = args.limit or 5  # Default to 5 relevant episodes
                        runner.logger.info(f"🚀 P2 OPTIMIZATION ACTIVE: Seeking {max_episodes} relevant episodes")
                        result = runner.process_episodes_optimized(max_episodes)
                    else:
                        runner.logger.error("No input provided and optimization disabled")
                        result = {
                            'success': False,
                            'error': 'No input provided',
                            'episodes_processed': 0,
                            'episodes': []
                        }

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
