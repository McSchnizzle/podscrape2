#!/usr/bin/env python3
"""
Full Pipeline Orchestrator - Orchestrates Individual Phase Scripts
Refactored to call individual phase scripts instead of duplicating logic.
This ensures DRY principle - identical code used by Web UI, CI/CD, and manual runs.
"""

import os
import sys
import json
import logging
import subprocess
import tempfile
from datetime import datetime, UTC
from pathlib import Path
import argparse
from typing import Any, Dict, Optional
from uuid import uuid4

# Add src to path for environment setup
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Set up environment via centralized entry point
from src.config.env import load_env, require_database_url
load_env()
require_database_url()

# Import centralized logging
from utils.logging_config import setup_phase_logging, move_legacy_logs_to_logs_dir
from src.publishing.retention_manager import create_retention_manager
from src.database.models import get_pipeline_run_repo, PipelineRun

class PipelineOrchestrator:
    """
    Orchestrates the complete pipeline by calling individual phase scripts
    """

    def __init__(self, log_file: str = None, phase_stop: str = None, dry_run: bool = False,
                 limit: int = None, days_back: int = 7, episode_guid: str = None, verbose: bool = False,
                 sequential: bool = False):

        # Move legacy logs on first run
        move_legacy_logs_to_logs_dir()

        # Set up centralized logging
        self.pipeline_logger = setup_phase_logging("orchestrator", verbose=verbose, console_output=True)
        self.logger = self.pipeline_logger.get_logger()
        self.log_file = str(self.pipeline_logger.get_log_file())

        # Load Web UI settings and merge with CLI arguments
        self.web_config = self._load_web_config()

        # Store configuration (with Web UI defaults if CLI not provided)
        self.phase_stop = phase_stop
        self.dry_run = dry_run
        self.limit = limit if limit is not None else self._get_web_setting('pipeline', 'max_episodes_per_run', 3)
        self.days_back = days_back if days_back != 7 else self._get_web_setting('pipeline', 'discovery_lookback_days', 7)
        self.episode_guid = episode_guid
        self.verbose = verbose
        self.sequential = sequential

        # Script paths - phase scripts are in the scripts directory
        self.scripts_dir = Path(__file__).parent

        # Log orchestrator start
        self.pipeline_logger.log_phase_start("Full RSS Podcast Pipeline Orchestrator")

        # Log configuration
        if self.dry_run:
            self.logger.info("🔍 DRY RUN MODE: No changes will be made")
        if self.limit:
            self.logger.info(f"📊 LIMIT: Processing max {self.limit} episodes")
        if self.episode_guid:
            self.logger.info(f"🎯 TARGET: Processing specific episode GUID: {self.episode_guid}")
        else:
            self.logger.info(f"📅 TIMEFRAME: Processing episodes from last {self.days_back} days")
        if self.verbose:
            self.logger.info("🔍 VERBOSE: Debug logging enabled")
        if self.sequential:
            self.logger.info("🔄 SEQUENTIAL: Parallel processing disabled for audio phase")

        # Initialize retention manager with WebConfig settings
        try:
            self.retention_manager = create_retention_manager()
            self.logger.info("📦 Retention manager initialized with WebConfig settings")
        except Exception as e:
            self.logger.warning(f"⚠️  Could not initialize retention manager: {e}")
            self.retention_manager = None

        # Initialize pipeline run tracking (Supabase) if available
        self.pipeline_run_repo = None
        self.pipeline_run_id = os.getenv('PIPELINE_RUN_ID') or str(uuid4())
        self.workflow_run_id = self._safe_parse_int(os.getenv('GITHUB_RUN_ID'))
        self.workflow_name = os.getenv('PIPELINE_WORKFLOW_NAME') or os.getenv('GITHUB_WORKFLOW')
        self.workflow_trigger = os.getenv('PIPELINE_TRIGGER') or os.getenv('GITHUB_EVENT_NAME')
        self.pipeline_run_started_at = datetime.now(UTC)
        self.pipeline_run_finished_at: Optional[datetime] = None
        self.pipeline_status = 'running'
        self.current_phase: Optional[str] = None
        self.phase_history: list[Dict[str, Any]] = []

        try:
            self.pipeline_run_repo = get_pipeline_run_repo()
            self.pipeline_run_repo.upsert(PipelineRun(
                id=self.pipeline_run_id,
                workflow_run_id=self.workflow_run_id,
                workflow_name=self.workflow_name,
                trigger=self.workflow_trigger,
                status=self.pipeline_status,
                started_at=self.pipeline_run_started_at,
                phase={'history': [], 'current': None}
            ))
            self.logger.debug(f"Pipeline run initialized with ID {self.pipeline_run_id}")
        except Exception as exc:
            self.logger.debug(f"Pipeline run tracking unavailable: {exc}")
            self.pipeline_run_repo = None

    def run_phase_script(self, script_name: str, input_data=None, **kwargs):
        """Run a phase script and return the result using file-based output contract."""

        script_path = self.scripts_dir / script_name
        if not script_path.exists():
            raise FileNotFoundError(f"Phase script not found: {script_path}")

        # Create temp file for JSON output (deterministic output channel)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tf:
            output_json_path = tf.name

        try:
            # Build command
            cmd = [sys.executable, str(script_path)]

            # Set environment variable to indicate orchestrated execution
            env = os.environ.copy()
            env['ORCHESTRATED_EXECUTION'] = '1'
            env['PIPELINE_RUN_ID'] = self.pipeline_run_id
            env['PIPELINE_PHASE'] = script_name

            # Add output flag for deterministic JSON output
            cmd.extend(['--output-json', output_json_path])

            # Add common flags
            if self.dry_run:
                cmd.append('--dry-run')
            if self.limit and script_name not in ['scripts/run_discovery.py', 'scripts/run_publishing.py', 'scripts/run_retention.py']:
                cmd.extend(['--limit', str(self.limit)])
            if self.verbose:
                cmd.append('--verbose')

            # Add script-specific flags
            if script_name == 'scripts/run_discovery.py':
                if self.days_back:
                    cmd.extend(['--days-back', str(self.days_back)])
                if self.episode_guid:
                    cmd.extend(['--episode-guid', self.episode_guid])
                if self.limit:
                    cmd.extend(['--limit', str(self.limit)])

            # Add sequential mode for audio and TTS phases (disables parallel processing)
            # This is important for single-server deployments like et01 where
            # parallel Whisper/FFmpeg processes can cause resource contention
            if script_name in ['scripts/run_audio.py', 'scripts/run_tts.py']:
                if self.sequential:
                    cmd.append('--no-parallel')

            # Add Web UI settings as CLI flags for scripts that support them
            if script_name == 'scripts/run_scoring.py':
                self._add_scoring_web_settings(cmd)

            # Add additional kwargs as flags
            for key, value in kwargs.items():
                if value is not None:
                    cmd.extend([f'--{key.replace("_", "-")}', str(value)])

            self.logger.info(f"Running: {' '.join(cmd)}")

            # Prepare input data
            input_json = None
            if input_data is not None:
                input_json = json.dumps(input_data)

            # Run the script with real-time log streaming
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                env=env
            )

            # Send input if provided
            if input_json:
                process.stdin.write(input_json)
                process.stdin.close()

            # Stream stdout to logs (no more JSON parsing needed!)
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break

                if line:
                    line = line.rstrip()
                    # Stream all output to log (logs only, no JSON mixing)
                    if any(level in line for level in ['INFO', 'WARNING', 'ERROR', 'DEBUG']):
                        self.logger.info(f"  {line}")

            # Wait for process to complete
            return_code = process.wait()

            # Read result from output file (deterministic!)
            if return_code == 0:
                try:
                    from src.utils.phase_output import read_phase_result
                    json_output = read_phase_result(output_json_path)
                    self.logger.info(f"Phase completed successfully")
                    return json_output
                except FileNotFoundError:
                    self.logger.error(f"Output file not found: {output_json_path}")
                    return {'success': False, 'error': 'Phase script did not write output file'}
                except json.JSONDecodeError as e:
                    self.logger.error(f"Invalid JSON in output file: {e}")
                    return {'success': False, 'error': f'Invalid JSON output: {e}'}
            else:
                self.logger.error(f"Phase failed with exit code {return_code}")
                # Try to read error result from file
                try:
                    from src.utils.phase_output import read_phase_result
                    error_result = read_phase_result(output_json_path)
                    return error_result
                except Exception:
                    return {'success': False, 'error': f'Script failed with exit code {return_code}'}

        except subprocess.TimeoutExpired as e:
            self.logger.error(f"Phase subprocess timeout: {e}")
            return {'success': False, 'error': f'Subprocess timeout: {e}'}
        except Exception as e:
            self.logger.error(f"Phase failed with exception: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            # Clean up temp file
            try:
                Path(output_json_path).unlink(missing_ok=True)
            except Exception:
                pass

    def _load_web_config(self):
        """Load WebConfigManager safely"""
        try:
            from src.config.web_config import WebConfigManager
            return WebConfigManager()
        except Exception as e:
            self.logger.warning(f"Could not load Web UI settings: {e}")
            return None

    def _get_web_setting(self, category: str, key: str, default: Any) -> Any:
        """Get Web UI setting with fallback to default"""
        if self.web_config:
            try:
                return self.web_config.get_setting(category, key, default)
            except Exception:
                pass
        return default

    def _add_scoring_web_settings(self, cmd: list):
        """Add Web UI settings for content scoring phase"""
        if not self.web_config:
            return

        # AI Content Scoring settings
        model = self._get_web_setting('ai_content_scoring', 'model', 'gpt-5-mini')
        max_tokens = self._get_web_setting('ai_content_scoring', 'max_tokens', 1000)
        max_input_tokens = self._get_web_setting('ai_content_scoring', 'max_input_tokens', 120000)
        max_episodes_per_batch = self._get_web_setting('ai_content_scoring', 'max_episodes_per_batch', 10)

        # Content filtering settings
        score_threshold = self._get_web_setting('content_filtering', 'score_threshold', 0.65)

        # Add as CLI flags
        cmd.extend(['--ai-model', str(model)])
        cmd.extend(['--max-tokens', str(max_tokens)])
        cmd.extend(['--max-input-tokens', str(max_input_tokens)])
        cmd.extend(['--max-episodes-per-batch', str(max_episodes_per_batch)])
        cmd.extend(['--score-threshold', str(score_threshold)])

    def _safe_parse_int(self, value: Optional[str]) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    def _record_phase_event(self, phase_name: str, status: str, detail: Optional[Dict[str, Any]] = None):
        if not self.pipeline_run_repo:
            return

        timestamp = datetime.now(UTC).isoformat()
        event: Dict[str, Any] = {
            'phase': phase_name,
            'status': status,
            'timestamp': timestamp,
        }
        if detail:
            event['detail'] = detail

        self.phase_history.append(event)

        if status in {'completed', 'failed', 'skipped'}:
            self.current_phase = None
        else:
            self.current_phase = phase_name

        phase_payload = {
            'history': self.phase_history[-50:],  # avoid unbounded growth
            'current': self.current_phase
        }

        try:
            self.pipeline_run_repo.upsert(PipelineRun(
                id=self.pipeline_run_id,
                workflow_run_id=self.workflow_run_id,
                workflow_name=self.workflow_name,
                trigger=self.workflow_trigger,
                status=self.pipeline_status,
                started_at=self.pipeline_run_started_at,
                finished_at=self.pipeline_run_finished_at,
                phase=phase_payload
            ))
        except Exception as exc:
            self.logger.debug(f"Failed to record pipeline phase event: {exc}")

    def _finalize_pipeline_run(self, conclusion: str, detail: Optional[Dict[str, Any]] = None):
        if not self.pipeline_run_repo:
            return

        self.pipeline_status = 'completed' if conclusion == 'success' else 'failed'
        self.pipeline_run_finished_at = datetime.now(UTC)

        notes = None
        if detail:
            try:
                notes = json.dumps(detail)
            except TypeError:
                pass

        try:
            self.pipeline_run_repo.upsert(PipelineRun(
                id=self.pipeline_run_id,
                workflow_run_id=self.workflow_run_id,
                workflow_name=self.workflow_name,
                trigger=self.workflow_trigger,
                status=self.pipeline_status,
                conclusion=conclusion,
                started_at=self.pipeline_run_started_at,
                finished_at=self.pipeline_run_finished_at,
                phase={'history': self.phase_history[-50:], 'current': None},
                notes=notes
            ))
        except Exception as exc:
            self.logger.debug(f"Failed to finalize pipeline run: {exc}")


    def run_pipeline(self):
        """Execute the complete pipeline by orchestrating phase scripts"""

        start_time = datetime.now()

        try:
            # Phase 1: Discovery
            self.logger.info("\n" + "="*80)
            self.logger.info("PHASE 1: EPISODE DISCOVERY")
            self.logger.info("="*80)

            self._record_phase_event('discovery', 'starting', {
                'days_back': self.days_back,
                'limit': self.limit,
                'episode_guid': self.episode_guid,
            })

            discovery_result = self.run_phase_script('scripts/run_discovery.py')

            if not discovery_result.get('success'):
                self.logger.error(f"Discovery phase failed: {discovery_result.get('error')}")
                self._record_phase_event('discovery', 'failed', {
                    'error': discovery_result.get('error')
                })
                return self._log_failure(start_time, "Discovery phase failed")

            episodes_found = discovery_result.get('episodes_found', 0)
            self.logger.info(f"📻 Episodes discovered: {episodes_found}")
            self._record_phase_event('discovery', 'completed', {
                'episodes_found': episodes_found
            })

            if episodes_found == 0:
                return self._log_success(start_time, episodes_found, [], [], [])

            if self.phase_stop == 'discovery':
                self.logger.info("Stopping after discovery phase as requested")
                return self._log_success(start_time, episodes_found, [], [], [])

            # Phase 2: Audio Processing
            self.logger.info("\n" + "="*80)
            self.logger.info("PHASE 2: AUDIO PROCESSING")
            self.logger.info("="*80)

            self._record_phase_event('audio', 'starting', {
                'episodes_in': episodes_found
            })

            audio_result = self.run_phase_script('scripts/run_audio.py', discovery_result)

            audio_failed = not audio_result.get('success')
            if audio_failed:
                self.logger.warning(f"⚠️  Audio phase failed: {audio_result.get('error')}")
                self.logger.info("📝 Continuing to digest phase to process already-scored episodes...")
                self._record_phase_event('audio', 'failed', {
                    'error': audio_result.get('error')
                })
                episodes_processed = 0
            else:
                episodes_processed = audio_result.get('episodes_processed', 0)
                self.logger.info(f"🎵 Episodes processed: {episodes_processed}")
                self._record_phase_event('audio', 'completed', {
                    'episodes_processed': episodes_processed
                })

            if self.phase_stop == 'audio':
                self.logger.info("Stopping after audio phase as requested")
                return self._log_success(start_time, episodes_found, [], [], [])

            # Phase 3: Digest Generation
            self.logger.info("\n" + "="*80)
            self.logger.info("PHASE 3: DIGEST GENERATION")
            self.logger.info("="*80)

            self._record_phase_event('digest', 'starting', {
                'date': datetime.now(UTC).date().isoformat()
            })

            digest_result = self.run_phase_script('scripts/run_digest.py')

            if not digest_result.get('success'):
                self.logger.error(f"Digest phase failed: {digest_result.get('error')}")
                self._record_phase_event('digest', 'failed', {
                    'error': digest_result.get('error')
                })
                return self._log_failure(start_time, "Digest phase failed")

            digests_generated = digest_result.get('digests_generated', 0)
            self.logger.info(f"📝 Digests generated: {digests_generated}")
            self._record_phase_event('digest', 'completed', {
                'digests_generated': digests_generated
            })

            if self.phase_stop == 'digest':
                self.logger.info("Stopping after digest phase as requested")
                return self._log_success(start_time, episodes_found, [], digest_result.get('digests', []), [])

            # Phase 4: TTS Audio Generation
            self.logger.info("\n" + "="*80)
            self.logger.info("PHASE 4: TTS AUDIO GENERATION")
            self.logger.info("="*80)

            self._record_phase_event('tts', 'starting', {
                'digests_in': digests_generated
            })

            tts_result = self.run_phase_script('scripts/run_tts.py')

            if not tts_result.get('success'):
                self.logger.warning(f"TTS phase failed: {tts_result.get('error')}")
                self.logger.info("📡 Continuing to publishing phase to publish any completed digests...")
                self._record_phase_event('tts', 'failed', {
                    'error': tts_result.get('error')
                })
                audio_generated = 0
            else:
                audio_generated = tts_result.get('audio_generated', 0)
                self.logger.info(f"🎤 Audio files generated: {audio_generated}")
                self._record_phase_event('tts', 'completed', {
                    'audio_generated': audio_generated
                })

            if self.phase_stop == 'tts':
                self.logger.info("Stopping after TTS phase as requested")
                return self._log_success(
                    start_time,
                    episodes_found,
                    [],
                    digest_result.get('digests', []),
                    tts_result.get('audio_results', []) if tts_result.get('success') else []
                )

            # Phase 5: Publishing
            self.logger.info("\n" + "="*80)
            self.logger.info("PHASE 5: PUBLISHING")
            self.logger.info("="*80)

            self._record_phase_event('publishing', 'starting', None)

            publishing_result = self.run_phase_script('scripts/run_publishing.py')

            if not publishing_result.get('success'):
                self.logger.warning(f"Publishing phase had issues: {publishing_result.get('error')}")
                self._record_phase_event('publishing', 'failed', {
                    'error': publishing_result.get('error')
                })
            else:
                self.logger.info(f"📡 Publishing completed successfully")
                self._record_phase_event('publishing', 'completed', None)

            # Phase 6: Retention Management
            # Cleans up old files, database records, and GitHub releases
            # Retention policies configured via web UI (web_settings table)
            self.logger.info("\n" + "="*80)
            self.logger.info("PHASE 6: RETENTION MANAGEMENT")
            self.logger.info("="*80)

            self._record_phase_event('retention', 'starting', None)

            retention_result = self.run_phase_script('scripts/run_retention.py')

            if not retention_result.get('success'):
                self.logger.warning(f"Retention phase had issues: {retention_result.get('error')}")
                self._record_phase_event('retention', 'failed', {
                    'error': retention_result.get('error')
                })
            else:
                cleanup_stats = retention_result.get('cleanup_stats', {})
                self.logger.info(f"🧹 Retention completed: {cleanup_stats.get('total_files', 0)} files, {cleanup_stats.get('total_mb', 0)} MB freed")
                self._record_phase_event('retention', 'completed', cleanup_stats)

            # Final summary
            return self._log_success(
                start_time,
                episodes_found,
                [],
                digest_result.get('digests', []),
                tts_result.get('audio_results', []) if tts_result.get('success') else []
            )

        except Exception as e:
            return self._log_failure(start_time, f"Pipeline failed: {e}")

    def _log_success(self, start_time, episodes_found, scored_episodes, digests, audio_results):
        """Log successful pipeline completion"""

        elapsed = datetime.now() - start_time

        self.logger.info("\n" + "="*100)
        self.logger.info("🎉 PIPELINE EXECUTION COMPLETE")
        self.logger.info("="*100)

        self.logger.info(f"⏱️  Total Runtime: {elapsed}")
        self.logger.info(f"📻 Episodes Found: {episodes_found}")
        self.logger.info(f"📊 Episodes Scored: {len(scored_episodes)}")
        self.logger.info(f"📝 Digests Generated: {len(digests)}")
        self.logger.info(f"🎵 Audio Files Generated: {len([r for r in audio_results if r.get('success')])}")

        summary = {
            'success': True,
            'episodes_found': episodes_found,
            'episodes_scored': len(scored_episodes),
            'digests_generated': len(digests),
            'audio_generated': len([r for r in audio_results if r.get('success')])
        }

        self._finalize_pipeline_run('success', summary)

        # Note: Retention cleanup is handled by dedicated Phase 6
        self.logger.info(f"\n📋 Log File: {self.log_file}")
        self.logger.info("🚀 Pipeline orchestration completed successfully!")

        return summary

    def _log_failure(self, start_time, error_message):
        """Log pipeline failure"""

        elapsed = datetime.now() - start_time

        self.logger.error(f"\n💥 PIPELINE FAILED after {elapsed}")
        self.logger.error(f"Error: {error_message}")
        self.logger.error(f"📋 Check log file for details: {self.log_file}")

        self._finalize_pipeline_run('failure', {'error': error_message})

        return {'success': False, 'error': error_message}

def main():
    parser = argparse.ArgumentParser(description='Run complete RSS podcast pipeline (orchestrator) - 6 phases')
    parser.add_argument('--log', help='Log file path', default=None)
    parser.add_argument('--phase', help='Stop after phase',
                       choices=['discovery','audio','digest','tts','publishing','retention'], default=None)

    # Enhanced Phase 1 CLI flags
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be processed without making changes')
    parser.add_argument('--limit', type=int, help='Limit number of episodes to process', default=None)
    parser.add_argument('--days-back', type=int, help='Only process episodes from N days back', default=7)
    parser.add_argument('--episode-guid', help='Process specific episode by GUID', default=None)
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    parser.add_argument('--sequential', action='store_true',
                       help='Disable parallel processing in audio phase (safer for single-server deployments)')

    args = parser.parse_args()

    orchestrator = PipelineOrchestrator(
        log_file=args.log,
        phase_stop=args.phase,
        dry_run=args.dry_run,
        limit=args.limit,
        days_back=args.days_back,
        episode_guid=args.episode_guid,
        verbose=args.verbose,
        sequential=args.sequential
    )

    orchestrator.run_pipeline()

if __name__ == '__main__':
    main()
