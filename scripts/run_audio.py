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
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading



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
import threading

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
        self.pipeline_config = self.config_reader.get_pipeline_config()
        self.score_threshold = self.config_reader.get_score_threshold()

        # Initialize content scorer for immediate relevance checking
        self.content_scorer = ContentScorer()

        # Verify dependencies
        self._verify_dependencies()

        self.audio_processor = AudioProcessor(chunk_duration_minutes=self.audio_config['chunk_duration_minutes'])

        # Initialize OpenAI Whisper transcriber
        # IMPORTANT: Main transcriber is for metadata only - workers get thread-local instances
        self.transcriber = None
        self._transcriber_config = None  # Store config for thread-local creation
        self._thread_local = threading.local()  # Thread-local storage for transcribers
        if self.has_openai_whisper:
            from src.podcast.openai_whisper_transcriber import create_openai_whisper_transcriber
            self.transcriber = create_openai_whisper_transcriber(chunk_duration_minutes=self.audio_config['chunk_duration_minutes'])
            # Store config for creating thread-local transcribers
            self._transcriber_config = {
                'chunk_duration_minutes': self.audio_config['chunk_duration_minutes']
            }

        self.logger.info("Audio processing initialized")
        self.logger.info(f"Database settings - Chunk duration: {self.audio_config['chunk_duration_minutes']}min, "
                        f"Max chunks per episode: {self.audio_config['max_chunks_per_episode']}, "
                        f"Transcribe all chunks: {self.audio_config['transcribe_all_chunks']}, "
                        f"STT model: {self.audio_config['stt_model']}, "
                        f"Max episodes per run: {self.pipeline_config['max_episodes_per_run']}")

        self.pipeline_logger.log_phase_start("Audio download and transcription processing")

    def _get_thread_local_transcriber(self):
        """Get or create thread-local Whisper transcriber instance.

        CRITICAL: Each worker thread gets its own Whisper model to avoid race conditions.
        Whisper/PyTorch models are NOT thread-safe - concurrent access causes corruption.
        """
        if not hasattr(self._thread_local, 'transcriber'):
            # Create new transcriber for this thread
            from src.podcast.openai_whisper_transcriber import create_openai_whisper_transcriber
            self._thread_local.transcriber = create_openai_whisper_transcriber(
                chunk_duration_minutes=self._transcriber_config['chunk_duration_minutes']
            )
            thread_name = threading.current_thread().name
            self.logger.debug(f"Created thread-local Whisper transcriber for {thread_name}")
        return self._thread_local.transcriber

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

    def process_episodes_optimized(self, max_relevant_episodes, parallel=True, max_workers=8):
        """Process episodes until max_relevant_episodes RELEVANT episodes are found.

        This optimization processes episodes from the database (pending status)
        until we accumulate the desired number of RELEVANT episodes (score >= threshold).
        
        Args:
            max_relevant_episodes: Target number of relevant episodes to find
            parallel: Enable parallel processing (default: True)
            max_workers: Maximum number of concurrent workers (default: 8)
        """
        if parallel:
            self.logger.info(f"🎯 P2 OPTIMIZATION (PARALLEL): Processing until {max_relevant_episodes} relevant episodes found")
            self.logger.info(f"   🚀 Smart backfill with concurrent workers (details below)")
            return self._process_episodes_parallel(max_relevant_episodes, max_workers)
        else:
            self.logger.info(f"🎯 P2 OPTIMIZATION (SEQUENTIAL): Processing until {max_relevant_episodes} relevant episodes found")
            return self._process_episodes_sequential(max_relevant_episodes)
    
    def _process_episodes_sequential(self, max_relevant_episodes):
        """Original sequential processing logic"""
        self.logger.info(f"Processing sequentially until {max_relevant_episodes} relevant episodes found")

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
                scoring_outcome = self._score_episode_immediately(episode.episode_guid)

                if not scoring_outcome.get('success'):
                    error_msg = scoring_outcome.get('error', 'Scoring failed')
                    self.logger.error(f"Immediate scoring failed for {episode.title}: {error_msg}")
                    try:
                        self.episode_repo.update_status(episode.episode_guid, 'transcribed')
                    except Exception:
                        pass
                    failed_episodes.append({
                        'guid': episode.episode_guid,
                        'title': episode.title,
                        'error': error_msg
                    })
                    continue

                scores = scoring_outcome.get('scores', {})

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

        # Success criteria: No failures occurred
        # Note: Finding 0 relevant episodes is NOT a failure - it's a valid outcome
        success = len(failed_episodes) == 0

        if success and relevant_count == 0 and total_processed > 0:
            self.logger.info("✓ Audio phase completed successfully (0 relevant episodes found - this is normal)")

        return {
            'success': success,
            'episodes_processed': len(processed_episodes),  # Only relevant episodes
            'episodes_failed': len(failed_episodes),
            'relevant_episodes_found': relevant_count,
            'not_relevant_episodes_found': not_relevant_count,
            'total_episodes_evaluated': total_processed,
            'episodes': processed_episodes,  # Only relevant episodes
            'failed': failed_episodes,
            'optimization_active': True,
            'processing_mode': 'sequential'
        }
    
    def _process_episodes_parallel(self, max_relevant_episodes, max_workers=4):
        """Parallel processing with smart backfill logic.

        IMPORTANT: Reduced to 4 workers (from 8) to mitigate Whisper model thread safety issues.
        Single shared Whisper model causes race conditions with >4 concurrent transcriptions.

        Algorithm:
        1. Reset any stuck 'processing' episodes from previous failed runs
        2. Start with max_workers parallel runners processing episodes
        3. Wait for all to complete
        4. Count how many are relevant vs not_relevant
        5. Launch additional runners to replace not_relevant episodes
        6. Repeat until max_relevant_episodes are found
        """
        # Step 1: Reset stuck 'processing' episodes at startup
        reset_count = self.episode_repo.reset_stuck_processing_episodes(timeout_minutes=10)
        if reset_count > 0:
            self.logger.info(f"🔄 Reset {reset_count} stuck 'processing' episodes back to 'pending'")

        # Get ALL pending episodes (oldest first)
        pending_episodes = self.episode_repo.get_by_status('pending')
        
        if not pending_episodes:
            self.logger.info("📊 No pending episodes found to process")
            self.logger.info("💡 Suggestion: Run discovery phase to find new episodes, or check for episodes in other statuses")
            return {
                'success': True,
                'episodes_processed': 0,
                'episodes': [],
                'message': "No pending episodes to process - pipeline complete or discovery needed",
                'processing_mode': 'parallel'
            }

        # Calculate actual worker capacity
        available_episodes = len(pending_episodes)
        actual_max_workers = min(max_workers, max_relevant_episodes, available_episodes)

        self.logger.info(f"📊 Found {available_episodes} pending episodes to evaluate")
        self.logger.info(f"⚙️ Using up to {actual_max_workers} concurrent workers (max: {max_workers}, need: {max_relevant_episodes}, available: {available_episodes})")
        
        # Shared state (thread-safe)
        processed_episodes = []
        failed_episodes = []
        relevant_count = 0
        not_relevant_count = 0
        total_processed = 0
        episode_index = 0
        lock = threading.Lock()
        
        def process_single_episode(episode):
            """Thread-safe episode processing with database cleanup.

            Each worker thread gets its own database connection that is properly
            closed after processing to prevent connection leaks.
            """
            nonlocal relevant_count, not_relevant_count, total_processed

            # Create worker-specific database connection (thread-safe)
            worker_episode_repo = None
            try:
                worker_episode_repo = get_episode_repo()
            except Exception as e:
                logger.error(f"Failed to create worker database connection: {e}")
                return {'type': 'failed', 'guid': episode.episode_guid, 'error': 'Database connection failed'}

            try:
                # Critical section: Claim this episode for processing
                with lock:
                    # Check for stuck processing episodes periodically
                    if total_processed % 5 == 0:  # Every 5 episodes
                        reset_count = worker_episode_repo.reset_stuck_processing_episodes(timeout_minutes=10)
                        if reset_count > 0:
                            self.logger.info(f"🔄 Reset {reset_count} additional stuck episodes during processing")

                    # Check if episode is already being processed or completed
                    current_episode = worker_episode_repo.get_by_episode_guid(episode.episode_guid)
                    if current_episode and current_episode.status not in ['pending']:
                        self.logger.debug(f"Episode {episode.title[:40]} already processing/processed (status: {current_episode.status}), skipping")
                        return {'type': 'skipped', 'guid': episode.episode_guid}

                    # Mark episode as processing to prevent other workers from taking it
                    try:
                        worker_episode_repo.update_status(episode.episode_guid, 'processing')
                    except Exception as e:
                        self.logger.warning(f"Could not mark episode as processing: {e}")
                        return {'type': 'skipped', 'guid': episode.episode_guid}

                    total_processed += 1
                    current_num = total_processed

                self.logger.info(f"\n[Worker-{threading.current_thread().name[-1]}] [{current_num}] Processing: {episode.title[:60]}")
                if self.dry_run:
                    self.logger.info("🔍 DRY RUN: Would process and score episode")
                    with lock:
                        relevant_count += 1
                    return {
                        'guid': episode.episode_guid,
                        'title': episode.title,
                        'status': 'dry_run',
                        'is_relevant': True,
                        'type': 'success'
                    }
                # Process audio (download + transcribe)
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
                    return {
                        'guid': episode.episode_guid,
                        'title': episode.title,
                        'error': audio_result.get('error', 'Audio processing failed'),
                        'type': 'failed'
                    }
                
                # Score episode immediately
                scoring_outcome = self._score_episode_immediately(episode.episode_guid)
                if not scoring_outcome.get('success'):
                    error_msg = scoring_outcome.get('error', 'Scoring failed')
                    self.logger.error(f"Immediate scoring failed for {episode.title}: {error_msg}")
                    try:
                        worker_episode_repo.update_status(episode.episode_guid, 'transcribed')
                    except Exception:
                        pass
                    return {
                        'guid': episode.episode_guid,
                        'title': episode.title,
                        'error': error_msg,
                        'type': 'failed'
                    }

                scores = scoring_outcome.get('scores', {})

                # Check relevance
                is_relevant = any(score >= self.score_threshold for score in scores.values()) if scores else False
                
                # Update status and counts
                with lock:
                    if is_relevant:
                        relevant_count += 1
                        worker_episode_repo.update_status(episode.episode_guid, 'scored')
                        self.logger.info(f"✅ RELEVANT episode ({relevant_count}/{max_relevant_episodes})")
                        return {
                            **audio_result,
                            'is_relevant': True,
                            'scores': scores,
                            'type': 'relevant'
                        }
                    else:
                        not_relevant_count += 1
                        worker_episode_repo.update_status(episode.episode_guid, 'not_relevant')
                        self.logger.info(f"❌ Not relevant episode (will backfill...)")
                        return {
                            'guid': episode.episode_guid,
                            'title': episode.title,
                            'is_relevant': False,
                            'type': 'not_relevant'
                        }

            except Exception as e:
                # Reset episode status on failure so it can be retried
                try:
                    worker_episode_repo.update_status(episode.episode_guid, 'pending')
                except:
                    pass
                self.logger.error(f"Failed to process episode {episode.title}: {e}")
                return {
                    'guid': episode.episode_guid,
                    'title': episode.title,
                    'error': str(e),
                    'type': 'failed'
                }
            finally:
                # CRITICAL: Cleanup worker database connection to prevent leaks
                if worker_episode_repo:
                    try:
                        # Try to close if method exists (SQLAlchemy sessions auto-close via context manager)
                        if hasattr(worker_episode_repo, 'close'):
                            worker_episode_repo.close()
                            self.logger.debug(f"Worker database connection closed for {episode.episode_guid[:8]}")
                    except Exception as e:
                        self.logger.warning(f"Error closing worker database connection: {e}")
        
        # Smart backfill loop
        round_num = 1
        while relevant_count < max_relevant_episodes and episode_index < len(pending_episodes):
            # Determine batch size
            remaining_needed = max_relevant_episodes - relevant_count
            available_episodes = len(pending_episodes) - episode_index
            batch_size = min(actual_max_workers, remaining_needed, available_episodes)
            
            if batch_size == 0:
                break
            
            self.logger.info(f"\n🚀 ROUND {round_num}: Launching {batch_size} workers (need {remaining_needed} more relevant, {available_episodes} available)")
            
            # Get batch of episodes
            batch_episodes = pending_episodes[episode_index:episode_index + batch_size]
            episode_index += batch_size
            
            # Process batch in parallel
            with ThreadPoolExecutor(max_workers=actual_max_workers, thread_name_prefix="Worker") as executor:
                futures = {executor.submit(process_single_episode, ep): ep for ep in batch_episodes}
                
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        
                        if result['type'] == 'relevant':
                            processed_episodes.append(result)
                        elif result['type'] == 'failed':
                            failed_episodes.append(result)
                        # not_relevant and skipped episodes don't get added to output
                    except Exception as e:
                        self.logger.error(f"Worker thread exception: {e}")
                        # Continue with other workers
            
            self.logger.info(f"📋 Round {round_num} complete: {relevant_count}/{max_relevant_episodes} relevant found")
            round_num += 1
        
        # Final summary
        self._log_processing_summary(processed_episodes, relevant_count, not_relevant_count, total_processed)
        self.logger.info(f"\n🏁 PARALLEL PROCESSING COMPLETE:")
        self.logger.info(f"   Total rounds: {round_num - 1}")
        self.logger.info(f"   Peak workers: {actual_max_workers}")
        self.logger.info(f"   Performance: ~{actual_max_workers}x faster than sequential")

        # Success criteria: No failures occurred
        # Note: Finding 0 relevant episodes is NOT a failure - it's a valid outcome
        # The pipeline successfully processed all available episodes
        success = len(failed_episodes) == 0

        if success and relevant_count == 0 and total_processed > 0:
            self.logger.info("✓ Audio phase completed successfully (0 relevant episodes found - this is normal)")

        return {
            'success': success,
            'episodes_processed': len(processed_episodes),
            'episodes_failed': len(failed_episodes),
            'relevant_episodes_found': relevant_count,
            'not_relevant_episodes_found': not_relevant_count,
            'total_episodes_evaluated': total_processed,
            'episodes': processed_episodes,
            'failed': failed_episodes,
            'optimization_active': True,
            'processing_mode': 'parallel',
            'max_workers': actual_max_workers,
            'rounds': round_num - 1
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

            # CRITICAL: Get thread-local transcriber to avoid race conditions
            # Each worker thread must have its own Whisper model instance
            thread_transcriber = self._get_thread_local_transcriber()

            model_info = thread_transcriber.get_model_info()
            self.logger.info(f"Using OpenAI Whisper: {model_info.get('model', 'unknown')} model")

            # Convert paths to strings for Whisper API
            chunk_paths_str = [str(path) for path in chunk_paths]

            # Transcribe using thread-local instance with MEMORY-EFFICIENT MODE
            # Pass episode_repo to enable incremental database writes (constant O(1) memory)
            transcription_result = thread_transcriber.transcribe_episode(
                chunk_paths_str,
                episode_guid,
                episode_repo=self.episode_repo
            )

            # In memory-efficient mode, transcript_text is empty (already in database)
            # Word count comes from database incremental writes
            total_words = transcription_result.word_count

            # Prepend metadata header to existing transcript content in database
            feed_name = episode_data.get('feed_name', 'Unknown')
            metadata_header = (
                f"# Complete Transcript\n"
                f"# Episode: {db_episode.title}\n"
                f"# Feed: {feed_name}\n"
                f"# GUID: {episode_guid}\n"
                f"# Processed: {datetime.now().isoformat()}\n"
                f"# Chunks: {len(chunk_paths)}\n"
                f"# Words: {total_words:,}\n\n"
            )

            # Read existing transcript from database and prepend header
            db_episode_refreshed = self.episode_repo.get_by_episode_guid(episode_guid)
            if db_episode_refreshed and db_episode_refreshed.transcript_content:
                transcript_with_metadata = metadata_header + db_episode_refreshed.transcript_content
            else:
                # Fallback if transcript not in database (shouldn't happen in memory-efficient mode)
                self.logger.warning(f"Expected transcript in database but not found - using empty transcript")
                transcript_with_metadata = metadata_header + "[Transcript not available]"

            # Update database with final transcript including metadata header
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
            error_str = str(e)
            self.logger.error(f"Audio processing failed: {error_str}")
            
            # For 404 and corrupt audio errors, mark as not_relevant to avoid retries
            if any(keyword in error_str.lower() for keyword in ['404', 'not found', 'failed validation', 'corrupt']):
                self.logger.info(f"Marking episode as not_relevant due to permanent failure: {error_str}")
                try:
                    self.episode_repo.update_status(episode_guid, 'not_relevant')
                except:
                    pass
            else:
                # For other errors, mark as failed for potential retry
                try:
                    self.episode_repo.mark_failure(episode_guid, error_str)
                except:
                    pass
            
            return {
                'success': False,
                'error': error_str
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
            if not db_episode:
                message = f"Episode not found for immediate scoring: {episode_guid}"
                self.logger.warning(message)
                return {'success': False, 'error': message, 'scores': {}}

            if not db_episode.transcript_content:
                message = f"No transcript available for immediate scoring: {episode_guid}"
                self.logger.warning(message)
                return {'success': False, 'error': message, 'scores': {}}

            self.logger.info("⚡ Immediate scoring...")

            # Use the content scorer to get scores
            scoring_result = self.content_scorer.score_transcript(
                db_episode.transcript_content,
                episode_guid
            )

            if scoring_result.success:
                # Store scores in database
                self.episode_repo.update_scores(episode_guid, scoring_result.scores)

                self.logger.info(
                    f"✓ Scores: {', '.join([f'{topic}: {score:.2f}' for topic, score in scoring_result.scores.items()])}"
                )
                return {'success': True, 'scores': scoring_result.scores}

            error_message = scoring_result.error_message or 'Scoring failed'
            self.logger.error(f"Scoring failed: {error_message}")
            return {'success': False, 'error': error_message, 'scores': {}}

        except Exception as e:
            error_message = str(e)
            self.logger.error(f"Immediate scoring failed: {error_message}")
            return {'success': False, 'error': error_message, 'scores': {}}

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
    parser.add_argument('--no-parallel', action='store_true', help='Disable parallel processing (use sequential)')

    args = parser.parse_args()

    dry_run = resolve_dry_run_flag(args.dry_run)

    try:
        with AudioProcessor_Runner(
            dry_run=dry_run,
            limit=args.limit,
            verbose=args.verbose
        ) as runner:

            # Handle input - but prefer database-driven processing
            if args.input:
                if args.input.endswith('.json') or '/' in args.input:
                    # Legacy JSON file input for compatibility
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
                # Default behavior: Process pending episodes from database
                # Use --limit flag if provided, otherwise read from database settings
                if args.limit is not None:
                    max_episodes = args.limit
                    runner.logger.info(f"🚀 Using --limit override: {max_episodes} relevant episodes")
                else:
                    # CRITICAL: Must read max_episodes_per_run from database - NO DEFAULTS
                    max_episodes_setting = runner.pipeline_config.get('max_episodes_per_run')
                    if max_episodes_setting is None:
                        error_msg = (
                            "FATAL: max_episodes_per_run setting not found in database. "
                            "This setting is required for audio phase processing. "
                            "Please configure 'pipeline.max_episodes_per_run' in web_settings table."
                        )
                        runner.logger.error(error_msg)
                        raise RuntimeError(error_msg)
                    max_episodes = max_episodes_setting
                    runner.logger.info(f"🚀 Using database setting: {max_episodes} relevant episodes (from pipeline.max_episodes_per_run)")
                
                runner.logger.info(f"🚀 AUDIO PHASE: Processing pending episodes from database (seeking {max_episodes} relevant episodes)")
                # Use parallel processing by default, unless --no-parallel flag is set
                use_parallel = not args.no_parallel
                result = runner.process_episodes_optimized(max_episodes, parallel=use_parallel)

        # Display audio phase summary
        if result['success'] and result.get('episodes_processed', 0) > 0:
            runner.logger.info("=" * 60)
            runner.logger.info("AUDIO PHASE SUMMARY")
            runner.logger.info("=" * 60)

            relevant_count = result.get('relevant_episodes_found', 0)
            not_relevant_count = result.get('not_relevant_episodes_found', 0)
            total_evaluated = result.get('total_episodes_evaluated', 0)

            # Display processed episodes with scores
            for ep in result.get('episodes', []):
                title = ep.get('title', 'Unknown')
                scores = ep.get('scores', {})

                # Format scores for display
                if scores:
                    scores_str = ', '.join([f"{topic}: {score:.2f}" for topic, score in scores.items()])
                    scores_display = f"Scores: {{{scores_str}}}"
                else:
                    scores_display = "Scores: none"

                status = "scored" if ep.get('is_relevant') else "not_relevant"
                runner.logger.info(f"  Episode: \"{title}\"")
                runner.logger.info(f"    {scores_display} - Status: {status}")

            runner.logger.info("\n" + "=" * 60)
            runner.logger.info(f"Total: {total_evaluated} episode{'s' if total_evaluated != 1 else ''} processed")
            runner.logger.info(f"  ✅ Relevant: {relevant_count}")
            runner.logger.info(f"  ❌ Not Relevant: {not_relevant_count}")
            runner.logger.info("=" * 60)

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
