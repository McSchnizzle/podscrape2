#!/usr/bin/env python3
"""
Audio Processing Phase Script - Download and Transcription
Independent script for Phase 2: Download audio, chunk, and transcribe episodes
Reads JSON input from discovery phase or direct episode data.
"""

import os
import re
import sys
import json
import logging
import time
import hashlib
from datetime import datetime
from pathlib import Path
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict
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

# Set up environment via centralized entry point
from src.utils.phase_bootstrap import bootstrap_phase
bootstrap_phase()

from src.database.models import get_episode_repo, Episode
from src.podcast.audio_processor import AudioProcessor
from src.utils.logging_config import setup_phase_logging
from src.scoring.content_scorer import ContentScorer
from src.topic_tracking.topic_extractor import StoryArcExtractor


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

        # Initialize story arc extractor for story arc tracking
        try:
            self.story_arc_extractor = StoryArcExtractor()
        except Exception as e:
            self.logger.warning(f"Story arc extractor initialization failed: {e}")
            self.story_arc_extractor = None

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

        # YouTube rate limiting - serialize requests with delay to avoid flagging
        self._youtube_lock = threading.Lock()
        self._youtube_last_request = 0.0
        self._youtube_delay_seconds = 5.0  # Minimum seconds between YouTube API calls

        # YouTube health tracking
        self.youtube_stats = {
            'attempted': 0,
            'transcript_api_success': 0,
            'ytdlp_subtitle_success': 0,
            'ytdlp_audio_success': 0,
            'failed': 0,
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

    def process_episodes_optimized(self, max_relevant_episodes, parallel=True, max_workers=8,
                                   max_total_episodes=None, prefetched_episodes=None):
        """Process episodes until max_relevant_episodes RELEVANT episodes are found.

        This optimization processes episodes from the database (pending status)
        until we accumulate the desired number of RELEVANT episodes (score >= threshold).

        Args:
            max_relevant_episodes: Target number of relevant episodes to find
            parallel: Enable parallel processing (default: True)
            max_workers: Maximum number of concurrent workers (default: 8)
            max_total_episodes: If set, cap total episodes processed regardless of relevance,
                                and order pending by feed priority (used by standalone audio cron).
            prefetched_episodes: If provided, use this list instead of fetching from DB.
                                 Overrides max_total_episodes. Used by --max-youtube/--max-rss.
        """
        if parallel:
            self.logger.info(f"🎯 P2 OPTIMIZATION (PARALLEL): Processing until {max_relevant_episodes} relevant episodes found")
            self.logger.info(f"   🚀 Smart backfill with concurrent workers (details below)")
            return self._process_episodes_parallel(max_relevant_episodes, max_workers,
                                                   max_total_episodes=max_total_episodes,
                                                   prefetched_episodes=prefetched_episodes)
        else:
            self.logger.info(f"🎯 P2 OPTIMIZATION (SEQUENTIAL): Processing until {max_relevant_episodes} relevant episodes found")
            return self._process_episodes_sequential(max_relevant_episodes,
                                                    max_total_episodes=max_total_episodes,
                                                    prefetched_episodes=prefetched_episodes)
    
    def _process_episodes_sequential(self, max_relevant_episodes, max_total_episodes=None,
                                     prefetched_episodes=None):
        """Original sequential processing logic"""
        self.logger.info(f"Processing sequentially until {max_relevant_episodes} relevant episodes found")

        # Pending source priority: prefetched list > priority-ordered cap > full pending
        if prefetched_episodes is not None:
            self.logger.info(f"   📌 Using prefetched list ({len(prefetched_episodes)} episodes)")
            pending_episodes = prefetched_episodes
        elif max_total_episodes is not None:
            self.logger.info(f"   📌 Priority-ordered fetch capped at {max_total_episodes} episodes")
            pending_episodes = self.episode_repo.get_pending_by_priority(limit=max_total_episodes)
        else:
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

                # Skip scoring for episodes that were skipped (e.g. YouTube quality check failed)
                if audio_result.get('skipped'):
                    self.logger.info(f"⏭️ Skipped: {audio_result.get('message', 'skipped')}")
                    not_relevant_count += 1
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

        # Phase succeeds if it ran to completion. Individual episode failures are reported
        # in the JSON output but don't fail the phase — only infrastructure errors caught
        # by the outer except block produce exit 1.
        success = True

        if relevant_count == 0 and total_processed > 0:
            self.logger.info("✓ Audio phase completed (0 relevant episodes found - this is normal)")
        if len(failed_episodes) > 0:
            self.logger.warning(f"⚠️ {len(failed_episodes)} episode(s) failed individually (phase still successful)")

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
    
    def _process_episodes_parallel(self, max_relevant_episodes, max_workers=4, max_total_episodes=None,
                                   prefetched_episodes=None):
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
        # 60-min threshold: long Whisper transcriptions on multi-hour episodes can
        # legitimately exceed shorter timeouts and would otherwise trigger split-brain resets.
        reset_count = self.episode_repo.reset_stuck_processing_episodes(timeout_minutes=60)
        if reset_count > 0:
            self.logger.info(f"🔄 Reset {reset_count} stuck 'processing' episodes back to 'pending'")

        # Pending source priority: prefetched list > priority-ordered cap > full pending
        if prefetched_episodes is not None:
            self.logger.info(f"📌 Using prefetched list ({len(prefetched_episodes)} episodes)")
            pending_episodes = prefetched_episodes
        elif max_total_episodes is not None:
            self.logger.info(f"📌 Priority-ordered fetch capped at {max_total_episodes} episodes")
            pending_episodes = self.episode_repo.get_pending_by_priority(limit=max_total_episodes)
        else:
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
                        reset_count = worker_episode_repo.reset_stuck_processing_episodes(timeout_minutes=60)
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

                # Skip scoring for episodes that were skipped (e.g. YouTube quality check failed)
                if audio_result.get('skipped'):
                    self.logger.info(f"⏭️ Skipped: {audio_result.get('message', 'skipped')}")
                    with lock:
                        not_relevant_count += 1
                    return {
                        'guid': episode.episode_guid,
                        'title': episode.title,
                        'status': 'not_relevant',
                        'is_relevant': False,
                        'type': 'skipped'
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

        # Phase succeeds if it ran to completion. Individual episode failures are reported
        # in the JSON output but don't fail the phase — only infrastructure errors caught
        # by the outer except block produce exit 1.
        success = True

        if len(failed_episodes) > 0:
            self.logger.warning(f"⚠️ {len(failed_episodes)} episode(s) failed individually (phase still successful)")

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
            'success': len(processed_episodes) > 0 or len(failed_episodes) == 0,
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

        # Skip YouTube Shorts - too short for meaningful digest content
        if self._is_youtube_short(db_episode):
            self.logger.info(f"⏭️ Skipping YouTube Short: {db_episode.title[:60]}")
            self.episode_repo.update_status(episode_guid, 'not_relevant')
            return {
                'success': True, 'skipped': True,
                'message': 'YouTube Short - too short for digest'
            }

        # Check if this is a YouTube episode - fetch transcript directly instead of audio
        if self._is_youtube_episode(episode_data, db_episode):
            return self._process_youtube_transcript(episode_data, db_episode)

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
                from src.config.web_config import WebConfigManager, SettingsKeys
                # Use a single config lookup and close immediately
                web_config = WebConfigManager()
                try:
                    transcribe_all = bool(web_config.get_setting(SettingsKeys.AudioProcessing.CATEGORY, SettingsKeys.AudioProcessing.TRANSCRIBE_ALL_CHUNKS, True))
                    max_chunks = int(web_config.get_setting(SettingsKeys.AudioProcessing.CATEGORY, SettingsKeys.AudioProcessing.MAX_CHUNKS_PER_EPISODE, 3))
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

            # Validate minimum transcript length to prevent low-quality content
            MIN_TRANSCRIPT_WORDS = 50
            if total_words < MIN_TRANSCRIPT_WORDS:
                self.logger.warning(
                    f"Transcript too short ({total_words} words, minimum {MIN_TRANSCRIPT_WORDS}). "
                    f"Episode may be intro/trailer/music-only. Marking as not_relevant."
                )
                self.episode_repo.update_status(episode_guid, 'not_relevant')

                # Track short transcript in workflow_errors for pattern analysis
                try:
                    from src.database.models import WorkflowError, get_workflow_error_repo
                    error_repo = get_workflow_error_repo()
                    error_repo.create(WorkflowError(
                        error_date=datetime.now().date(),
                        occurred_at=datetime.now(),
                        run_id=f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                        error_category='short_transcript',
                        phase='audio',
                        error_message=f"Transcript too short: {total_words} words (min {MIN_TRANSCRIPT_WORDS})",
                        severity='warning',
                        feed_id=db_episode.feed_id,
                        episode_id=db_episode.id,
                        episode_title=db_episode.title,
                    ))
                except Exception as track_err:
                    self.logger.debug(f"Failed to track short transcript: {track_err}")

                return {
                    'success': True,
                    'guid': episode_guid,
                    'title': db_episode.title,
                    'status': 'not_relevant',
                    'skipped': True,
                    'message': f'Transcript too short ({total_words} words) - likely not substantive content'
                }

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

    def _is_youtube_short(self, db_episode):
        """Detect YouTube Shorts - too short for meaningful digest content."""
        return 'youtube.com/shorts/' in (db_episode.audio_url or '')

    def _is_youtube_episode(self, episode_data, db_episode):
        """Detect whether this episode is from a YouTube channel (excludes Shorts)."""
        if self._is_youtube_short(db_episode):
            return False
        # Check feed_type from discovery data
        if episode_data.get('feed_type') == 'youtube':
            return True
        # Check audio_url pattern as fallback
        audio_url = db_episode.audio_url or ''
        return ('youtube.com/watch' in audio_url or
                'youtu.be/' in audio_url)

    def _extract_youtube_video_id(self, url):
        """Extract YouTube video ID from various URL formats."""
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
            r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        ]
        for pattern in patterns:
            match = re.search(pattern, url or '')
            if match:
                return match.group(1)
        return None

    def _process_youtube_transcript(self, episode_data, db_episode):
        """Process a YouTube episode by fetching its transcript directly (no audio download)."""
        episode_guid = db_episode.episode_guid
        video_id = self._extract_youtube_video_id(db_episode.audio_url)

        if not video_id:
            self.logger.warning(f"Could not extract video ID from URL: {db_episode.audio_url}")
            self.episode_repo.mark_failure(episode_guid, "Could not extract YouTube video ID")
            return {'success': False, 'error': 'Could not extract YouTube video ID'}

        # Rate limit YouTube requests - serialize across all worker threads
        with self._youtube_lock:
            now = time.time()
            elapsed = now - self._youtube_last_request
            if elapsed < self._youtube_delay_seconds:
                wait = self._youtube_delay_seconds - elapsed
                self.logger.info(f"⏳ YouTube rate limit: waiting {wait:.1f}s before next request")
                time.sleep(wait)
            self._youtube_last_request = time.time()

        self.logger.info(f"📺 YouTube episode detected - fetching transcript for video: {video_id}")
        self.youtube_stats['attempted'] += 1
        transcript_source = 'transcript_api'

        try:
            # Use the existing TranscriptProcessor
            from src.youtube.transcript_processor import TranscriptProcessor

            processor = TranscriptProcessor()
            transcript_data = processor.fetch_transcript(video_id)

            if transcript_data:
                self.youtube_stats['transcript_api_success'] += 1
            else:
                self.logger.warning(f"YouTube transcript API failed for {video_id} - trying yt-dlp fallback...")
                transcript_data = self._ytdlp_subtitle_fallback(video_id)
                if transcript_data:
                    self.youtube_stats['ytdlp_subtitle_success'] += 1
                    transcript_source = 'ytdlp_subtitles'

            if not transcript_data:
                self.logger.warning(f"All transcript methods failed for YouTube video {video_id} - trying audio download...")
                audio_result = self._ytdlp_audio_fallback(video_id, episode_guid, db_episode, episode_data)
                if audio_result:
                    self.youtube_stats['ytdlp_audio_success'] += 1
                    return audio_result
                # All fallbacks exhausted - mark as failed (NOT not_relevant)
                self.youtube_stats['failed'] += 1
                self.logger.error(f"All YouTube transcript/audio methods failed for {video_id}")
                self.episode_repo.mark_failure(episode_guid, f"All YouTube transcript methods failed for {video_id}")
                return {
                    'success': False, 'guid': episode_guid, 'title': db_episode.title,
                    'error': f'All YouTube transcript methods failed for video {video_id}'
                }

            # Validate transcript quality
            is_valid, reason = processor.validate_transcript_quality(transcript_data)
            if not is_valid:
                self.logger.warning(f"YouTube transcript quality check failed: {reason} - trying yt-dlp fallback...")
                ytdlp_data = self._ytdlp_subtitle_fallback(video_id)
                if ytdlp_data:
                    is_valid_2, reason_2 = processor.validate_transcript_quality(ytdlp_data)
                    if is_valid_2:
                        transcript_data = ytdlp_data
                        is_valid = True
                        self.logger.info(f"yt-dlp subtitle fallback passed quality check for {video_id}")

                if not is_valid:
                    # Quality-insufficient transcripts are a permanent rejection: a 152s video
                    # won't grow to 180s, a 16-word transcript won't sprout content. Mark
                    # not_relevant (terminal) so we don't re-fetch on every cron run, and
                    # return success so the phase-level exit code stays clean.
                    self.youtube_stats['failed'] += 1
                    self.logger.warning(f"YouTube transcript quality insufficient after all attempts: {reason}")
                    self.episode_repo.update_status(episode_guid, 'not_relevant')
                    return {
                        'success': True, 'guid': episode_guid, 'title': db_episode.title,
                        'status': 'not_relevant', 'skipped': True,
                        'message': f'YouTube transcript quality insufficient: {reason}'
                    }

            # Extract plain text and build transcript with metadata header
            transcript_text = processor.get_transcript_text(transcript_data)
            total_words = transcript_data.word_count

            feed_name = episode_data.get('feed_name', 'Unknown')
            transcript_with_metadata = (
                f"# Complete Transcript\n"
                f"# Episode: {db_episode.title}\n"
                f"# Feed: {feed_name}\n"
                f"# Source: YouTube ({video_id})\n"
                f"# GUID: {episode_guid}\n"
                f"# Language: {transcript_data.language}\n"
                f"# Auto-generated: {transcript_data.is_auto_generated}\n"
                f"# Duration: {transcript_data.total_duration:.0f}s\n"
                f"# Processed: {datetime.now().isoformat()}\n"
                f"# Words: {total_words:,}\n\n"
                + transcript_text
            )

            # Store transcript in database
            self.episode_repo.update_transcript(episode_guid, None, total_words, transcript_with_metadata)

            # Update duration from transcript data if available
            if transcript_data.total_duration > 0 and not db_episode.duration_seconds:
                try:
                    from src.database.models import get_database_manager
                    from src.database.sqlalchemy_models import Episode as EpisodeModel
                    db_manager = get_database_manager()
                    with db_manager.get_session() as session:
                        ep = session.query(EpisodeModel).filter(
                            EpisodeModel.episode_guid == episode_guid
                        ).first()
                        if ep:
                            ep.duration_seconds = int(transcript_data.total_duration)
                            session.commit()
                except Exception as dur_err:
                    self.logger.debug(f"Failed to update duration: {dur_err}")

            self.logger.info(f"✅ YouTube transcript complete: {total_words:,} words, {transcript_data.total_duration:.0f}s")

            # Apply minimum transcript length check (same as audio path)
            MIN_TRANSCRIPT_WORDS = 50
            if total_words < MIN_TRANSCRIPT_WORDS:
                self.logger.warning(
                    f"YouTube transcript too short ({total_words} words, minimum {MIN_TRANSCRIPT_WORDS}). "
                    f"Marking as not_relevant."
                )
                self.episode_repo.update_status(episode_guid, 'not_relevant')
                return {
                    'success': True, 'guid': episode_guid, 'title': db_episode.title,
                    'status': 'not_relevant', 'skipped': True,
                    'message': f'YouTube transcript too short ({total_words} words)'
                }

            return {
                'success': True,
                'guid': episode_guid,
                'title': db_episode.title,
                'status': 'transcribed',
                'transcript_path': None,
                'transcript_words': total_words,
                'chunks_processed': 0,
                'source': 'youtube'
            }

        except Exception as e:
            error_str = str(e)
            self.youtube_stats['failed'] += 1
            self.logger.error(f"YouTube transcript fetch failed: {error_str}")
            self.episode_repo.mark_failure(episode_guid, f"YouTube transcript error: {error_str}")
            return {'success': False, 'error': error_str}

    def _ytdlp_subtitle_fallback(self, video_id):
        """Fallback: fetch subtitles via yt-dlp when transcript API fails.
        Returns a TranscriptData-like object or None."""
        try:
            from src.youtube.ytdlp_fetcher import YtdlpFetcher
            from src.youtube.transcript_processor import TranscriptData, TranscriptSegment
            from datetime import datetime

            # Rate limit before fallback attempt
            time.sleep(self._youtube_delay_seconds)

            fetcher = YtdlpFetcher()
            result = fetcher.fetch_subtitles(video_id)

            if result.success and result.word_count > 0:
                self.logger.info(f"yt-dlp subtitle fallback succeeded for {video_id}: {result.word_count} words")
                return TranscriptData(
                    video_id=video_id,
                    language=result.language or 'en',
                    segments=[TranscriptSegment(text=result.transcript_text, start=0.0, duration=0.0)],
                    total_duration=0.0,
                    word_count=result.word_count,
                    is_auto_generated=result.is_generated,
                    fetch_timestamp=datetime.now()
                )
            else:
                self.logger.warning(f"yt-dlp subtitle fallback failed for {video_id}: {result.error_message}")
                return None
        except Exception as e:
            self.logger.warning(f"yt-dlp subtitle fallback error for {video_id}: {e}")
            return None

    def _ytdlp_audio_fallback(self, video_id, episode_guid, db_episode, episode_data):
        """Fallback: download audio via yt-dlp and transcribe with Whisper.
        Returns an audio_result dict or None if it fails."""
        try:
            from src.youtube.ytdlp_fetcher import YtdlpFetcher
            import tempfile

            self.logger.info(f"Attempting yt-dlp audio download for {video_id}...")
            time.sleep(self._youtube_delay_seconds)  # Rate limit before YouTube request
            fetcher = YtdlpFetcher()

            with tempfile.TemporaryDirectory() as tmpdir:
                result = fetcher.download_audio(video_id, tmpdir)

                if not result.success:
                    self.logger.warning(f"yt-dlp audio download failed for {video_id}: {result.error_message}")
                    return None

                self.logger.info(f"yt-dlp audio downloaded for {video_id}, processing through Whisper...")

                # Chunk and transcribe through the regular audio pipeline
                chunk_paths = self.audio_processor.chunk_audio(result.audio_path, episode_guid)
                self.logger.info(f"Chunked into {len(chunk_paths)} pieces")

                # Transcribe all chunks
                full_transcript = ""
                for i, chunk_path in enumerate(chunk_paths):
                    self.logger.info(f"  Transcribing chunk {i+1}/{len(chunk_paths)}...")
                    chunk_transcript = self.audio_processor.transcribe_chunk(chunk_path)
                    if chunk_transcript:
                        full_transcript += " " + chunk_transcript

                total_words = len(full_transcript.split())
                if total_words < 50:
                    self.logger.warning(f"yt-dlp audio transcript too short ({total_words} words)")
                    return None

                # Store transcript in database
                feed_name = episode_data.get('feed_name', 'Unknown')
                transcript_with_metadata = (
                    f"# Complete Transcript\n"
                    f"# Episode: {db_episode.title}\n"
                    f"# Feed: {feed_name}\n"
                    f"# Source: YouTube audio via yt-dlp ({video_id})\n"
                    f"# GUID: {episode_guid}\n"
                    f"# Processed: {datetime.now().isoformat()}\n"
                    f"# Words: {total_words:,}\n\n"
                    + full_transcript.strip()
                )

                self.episode_repo.update_transcript(episode_guid, None, total_words, transcript_with_metadata)
                self.logger.info(f"yt-dlp audio fallback succeeded for {video_id}: {total_words:,} words")

                return {
                    'success': True,
                    'guid': episode_guid,
                    'title': db_episode.title,
                    'status': 'transcribed',
                    'transcript_path': None,
                    'transcript_words': total_words,
                    'chunks_processed': len(chunk_paths),
                    'source': 'youtube_audio_fallback'
                }

        except Exception as e:
            self.logger.warning(f"yt-dlp audio fallback error for {video_id}: {e}")
            return None

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

            # Delete original audio file - must match the same id-derivation rule as
            # AudioProcessor.download_audio (md5 of GUID, first 6 hex chars).
            episode_id = hashlib.md5(episode_guid.encode()).hexdigest()[:6]
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

            MIN_SCORING_CHARS = 500
            transcript_len = len(db_episode.transcript_content or '')
            if not db_episode.transcript_content or transcript_len < MIN_SCORING_CHARS:
                message = f"Transcript too short for scoring ({transcript_len} chars, minimum {MIN_SCORING_CHARS}): {episode_guid}"
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

                # Extract story arcs for tracking (non-blocking)
                self._extract_story_arcs_for_tracking(episode_guid, db_episode.transcript_content, scoring_result.scores)

                return {'success': True, 'scores': scoring_result.scores}

            error_message = scoring_result.error_message or 'Scoring failed'
            self.logger.error(f"Scoring failed: {error_message}")
            return {'success': False, 'error': error_message, 'scores': {}}

        except Exception as e:
            error_message = str(e)
            self.logger.error(f"Immediate scoring failed: {error_message}")
            return {'success': False, 'error': error_message, 'scores': {}}

    def _extract_story_arcs_for_tracking(self, episode_guid: str, transcript: str, scores: Dict[str, float]):
        """
        Extract story arcs for tracking if enabled (non-blocking).

        Args:
            episode_guid: Episode GUID
            transcript: Full episode transcript
            scores: Dictionary of topic scores
        """
        if not self.story_arc_extractor:
            self.logger.debug("Story arc extractor not available, skipping story arc extraction")
            return

        try:
            # Get topics from database that have topic tracking enabled
            from src.database.sqlalchemy_models import Topic
            from src.database.models import get_database_manager, get_episode_repo

            db_manager = get_database_manager()
            episode_repo = get_episode_repo()

            # Get episode details for the new API
            episode = episode_repo.get_by_episode_guid(episode_guid)
            if not episode:
                self.logger.warning(f"Episode not found for story arc extraction: {episode_guid}")
                return

            with db_manager.get_session() as session:
                # Query for topics with enable_topic_tracking=True
                topics_with_tracking = session.query(Topic).filter(
                    Topic.enable_topic_tracking == True,
                    Topic.is_active == True
                ).all()

                if not topics_with_tracking:
                    self.logger.debug("No topics have story arc tracking enabled")
                    return

                # Extract story arcs for each relevant digest topic
                arc_count = 0
                for topic in topics_with_tracking:
                    topic_name = topic.name
                    topic_score = scores.get(topic_name, 0.0)

                    # Only extract if score is above threshold
                    if topic_score >= self.score_threshold:
                        try:
                            self.logger.info(f"🔍 Extracting story arcs for '{topic_name}' (score: {topic_score:.2f})")

                            extracted_arcs = self.story_arc_extractor.extract_and_store_story_arcs(
                                episode_id=episode.id,
                                episode_guid=episode_guid,
                                feed_id=episode.feed_id,
                                digest_topic=topic_name,
                                transcript=transcript,
                                episode_title=episode.title,
                                episode_published_date=episode.published_date,
                                relevance_score=topic_score
                            )

                            arc_count += len(extracted_arcs)
                            new_arcs = len([a for a in extracted_arcs if a.get('is_new')])
                            continued_arcs = len([a for a in extracted_arcs if not a.get('is_new')])
                            self.logger.info(
                                f"✓ Story arcs for '{topic_name}': {new_arcs} new, {continued_arcs} continued"
                            )

                        except Exception as e:
                            # Non-blocking: log warning but continue
                            self.logger.warning(
                                f"Story arc extraction failed for '{topic_name}': {e}"
                            )
                            continue

                if arc_count > 0:
                    self.logger.info(f"📋 Total story arcs processed: {arc_count}")

        except Exception as e:
            # Non-blocking: log warning but don't fail the pipeline
            self.logger.warning(f"Story arc extraction process failed: {e}")

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

        # YouTube feed health summary
        yt = self.youtube_stats
        if yt['attempted'] > 0:
            yt_success = yt['transcript_api_success'] + yt['ytdlp_subtitle_success'] + yt['ytdlp_audio_success']
            self.logger.info(f"\n   📺 YOUTUBE FEED HEALTH:")
            self.logger.info(f"      Attempted: {yt['attempted']}")
            self.logger.info(f"      Succeeded: {yt_success} ({100*yt_success//yt['attempted']}%)")
            self.logger.info(f"        - Transcript API: {yt['transcript_api_success']}")
            self.logger.info(f"        - yt-dlp subtitles: {yt['ytdlp_subtitle_success']}")
            self.logger.info(f"        - yt-dlp audio: {yt['ytdlp_audio_success']}")
            self.logger.info(f"      Failed: {yt['failed']}")
            if yt['failed'] > yt['attempted'] * 0.5:
                self.logger.warning(f"      ⚠️ HIGH YOUTUBE FAILURE RATE ({100*yt['failed']//yt['attempted']}%) - possible IP blocking or API issues")

def main():
    parser = argparse.ArgumentParser(description='Audio Processing Phase')
    parser.add_argument('input', nargs='?', help='Input JSON file from discovery phase or episode GUID')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be processed')
    parser.add_argument('--limit', type=int, help='Limit number of episodes')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    parser.add_argument('--output-json', help='Output JSON file path (default: stdout)')
    parser.add_argument('--no-parallel', action='store_true', help='Disable parallel processing (use sequential)')
    parser.add_argument('--max-total-episodes', type=int, default=None,
                       help='Cap total episodes processed (regardless of relevance), priority-ordered. Used by standalone audio cron.')
    parser.add_argument('--max-youtube', type=int, default=None,
                       help='Cap YouTube episodes processed per run. Combine with --max-rss for balanced fetch.')
    parser.add_argument('--max-rss', type=int, default=None,
                       help='Cap RSS (non-YouTube) episodes processed per run. Combine with --max-youtube for balanced fetch.')

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
                
                # Resolve fetch strategy:
                # 1. --max-youtube/--max-rss → balanced fetch from each feed type
                # 2. --max-total-episodes → priority-ordered cap regardless of feed type
                # 3. neither → original "find N relevant" behavior across all pending
                prefetched = None
                max_total = args.max_total_episodes
                if args.max_youtube is not None or args.max_rss is not None:
                    yt_n = args.max_youtube or 0
                    rss_n = args.max_rss or 0
                    runner.logger.info(f"🚀 AUDIO PHASE (standalone, balanced): up to {yt_n} YouTube + {rss_n} RSS episodes")
                    prefetched = runner.episode_repo.get_pending_balanced(
                        youtube_limit=args.max_youtube,
                        rss_limit=args.max_rss
                    )
                    runner.logger.info(f"   📊 Prefetch returned {len(prefetched)} pending episodes")
                    max_episodes = max(len(prefetched), 1)  # cap relevant target at fetch size
                elif max_total is not None:
                    runner.logger.info(f"🚀 AUDIO PHASE (standalone): Processing up to {max_total} total episodes from database (priority-ordered)")
                    max_episodes = max_total  # also cap relevant target so processor stops cleanly
                else:
                    runner.logger.info(f"🚀 AUDIO PHASE: Processing pending episodes from database (seeking {max_episodes} relevant episodes)")
                # Use parallel processing by default, unless --no-parallel flag is set
                use_parallel = not args.no_parallel
                result = runner.process_episodes_optimized(max_episodes, parallel=use_parallel,
                                                          max_total_episodes=max_total,
                                                          prefetched_episodes=prefetched)

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

        # Output JSON result (file or stdout)
        from src.utils.phase_output import write_phase_result
        write_phase_result(result, args.output_json)

        # Exit code
        sys.exit(0 if result['success'] else 1)

    except Exception as e:
        error_result = {
            'success': False,
            'error': str(e),
            'episodes_processed': 0,
            'episodes': []
        }

        # Output JSON error result (file or stdout)
        from src.utils.phase_output import write_phase_result
        write_phase_result(error_result, args.output_json)

        sys.exit(1)

if __name__ == '__main__':
    main()
