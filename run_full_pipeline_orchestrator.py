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
from datetime import datetime
from pathlib import Path
import argparse

# Add src to path for environment setup
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Set up environment
from dotenv import load_dotenv
load_dotenv()
from src.config.env import require_database_url
require_database_url()

# Import centralized logging
from utils.logging_config import setup_phase_logging, move_legacy_logs_to_logs_dir
from src.publishing.retention_manager import create_retention_manager

class PipelineOrchestrator:
    """
    Orchestrates the complete pipeline by calling individual phase scripts
    """

    def __init__(self, log_file: str = None, phase_stop: str = None, dry_run: bool = False,
                 limit: int = None, days_back: int = 7, episode_guid: str = None, verbose: bool = False):

        # Move legacy logs on first run
        move_legacy_logs_to_logs_dir()

        # Set up centralized logging
        self.pipeline_logger = setup_phase_logging("orchestrator", verbose=verbose, console_output=True)
        self.logger = self.pipeline_logger.get_logger()
        self.log_file = str(self.pipeline_logger.get_log_file())

        # Store configuration
        self.phase_stop = phase_stop
        self.dry_run = dry_run
        self.limit = limit
        self.days_back = days_back
        self.episode_guid = episode_guid
        self.verbose = verbose

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

        # Initialize retention manager with WebConfig settings
        try:
            self.retention_manager = create_retention_manager()
            self.logger.info("📦 Retention manager initialized with WebConfig settings")
        except Exception as e:
            self.logger.warning(f"⚠️  Could not initialize retention manager: {e}")
            self.retention_manager = None

    def run_phase_script(self, script_name: str, input_data=None, **kwargs):
        """Run a phase script and return the result"""

        script_path = self.scripts_dir / script_name
        if not script_path.exists():
            raise FileNotFoundError(f"Phase script not found: {script_path}")

        # Build command
        cmd = ['python3', str(script_path)]

        # Set environment variable to indicate orchestrated execution (to skip log cleanup)
        env = os.environ.copy()
        env['ORCHESTRATED_EXECUTION'] = '1'

        # Add output flag for orchestrator compatibility - use stdout
        # (no need to specify --output since default is stdout)

        # Add common flags
        if self.dry_run:
            cmd.append('--dry-run')
        if self.limit and script_name not in ['scripts/run_discovery.py', 'scripts/run_publishing.py']:  # Discovery has its own limit handling, Publishing doesn't support limit
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

        # Add additional kwargs as flags
        for key, value in kwargs.items():
            if value is not None:
                cmd.extend([f'--{key.replace("_", "-")}', str(value)])

        self.logger.info(f"🚀 Running: {' '.join(cmd)}")

        try:
            # Prepare input data
            input_json = None
            if input_data is not None:
                input_json = json.dumps(input_data)

            # Run the script with real-time output streaming
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Combine stderr with stdout
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True,
                env=env  # Pass environment with orchestration flag
            )

            # Send input if provided
            if input_json:
                process.stdin.write(input_json)
                process.stdin.close()

            # Stream output in real-time without timeout
            # For production: audio processing of multi-hour podcasts cannot have arbitrary time limits
            stdout_lines = []
            json_output = None

            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break

                if line:
                    line = line.rstrip()
                    stdout_lines.append(line)

                    # Try to parse as JSON (for final output)
                    if line.startswith('{') and line.endswith('}'):
                        try:
                            json_output = json.loads(line)
                        except json.JSONDecodeError:
                            pass

                    # Stream progress to log (filter out JSON output lines)
                    if not (line.startswith('{') and line.endswith('}')):
                        # Only show logs from script, not JSON output
                        if any(level in line for level in ['INFO', 'WARNING', 'ERROR', 'DEBUG']):
                            self.logger.info(f"  {line}")
                    else:
                        # This is likely JSON output - don't log it but ensure we capture it
                        self.logger.debug(f"Captured potential JSON output: {line[:100]}...")

            # Wait for process to complete
            return_code = process.wait()

            # Parse final output
            if return_code == 0:
                if json_output:
                    self.logger.info(f"✅ Phase completed successfully")
                    return json_output
                else:
                    # Try to find JSON in the last few lines
                    for line in reversed(stdout_lines[-10:]):
                        if line.startswith('{') and line.endswith('}'):
                            try:
                                json_output = json.loads(line)
                                self.logger.info(f"✅ Phase completed successfully")
                                return json_output
                            except json.JSONDecodeError:
                                continue

                    self.logger.error(f"No valid JSON output found from {script_name}")
                    return {'success': False, 'error': 'No valid JSON output'}
            else:
                self.logger.error(f"❌ Phase failed with exit code {return_code}")
                # Look for error JSON in output
                for line in reversed(stdout_lines[-10:]):
                    if line.startswith('{') and line.endswith('}'):
                        try:
                            error_data = json.loads(line)
                            return error_data
                        except json.JSONDecodeError:
                            continue

                return {'success': False, 'error': f'Script failed with exit code {return_code}'}

        except subprocess.TimeoutExpired as e:
            # This should not happen since we removed timeouts, but keep for subprocess.wait() calls
            self.logger.error(f"❌ Phase subprocess timeout: {e}")
            return {'success': False, 'error': f'Subprocess timeout: {e}'}
        except Exception as e:
            self.logger.error(f"❌ Phase failed with exception: {e}")
            return {'success': False, 'error': str(e)}

    def run_pipeline(self):
        """Execute the complete pipeline by orchestrating phase scripts"""

        start_time = datetime.now()

        try:
            # Phase 1: Discovery
            self.logger.info("\n" + "="*80)
            self.logger.info("PHASE 1: EPISODE DISCOVERY")
            self.logger.info("="*80)

            discovery_result = self.run_phase_script('scripts/run_discovery.py')

            if not discovery_result.get('success'):
                self.logger.error(f"Discovery phase failed: {discovery_result.get('error')}")
                return self._log_failure(start_time, "Discovery phase failed")

            episodes_found = discovery_result.get('episodes_found', 0)
            self.logger.info(f"📻 Episodes discovered: {episodes_found}")

            if episodes_found == 0:
                return self._log_success(start_time, episodes_found, [], [], [])

            if self.phase_stop == 'discovery':
                self.logger.info("Stopping after discovery phase as requested")
                return

            # Phase 2: Audio Processing
            self.logger.info("\n" + "="*80)
            self.logger.info("PHASE 2: AUDIO PROCESSING")
            self.logger.info("="*80)

            audio_result = self.run_phase_script('scripts/run_audio.py', discovery_result)

            if not audio_result.get('success'):
                self.logger.error(f"Audio phase failed: {audio_result.get('error')}")
                return self._log_failure(start_time, "Audio phase failed")

            episodes_processed = audio_result.get('episodes_processed', 0)
            self.logger.info(f"🎵 Episodes processed: {episodes_processed}")

            if self.phase_stop == 'audio':
                self.logger.info("Stopping after audio phase as requested")
                return

            # Phase 3: Content Scoring
            self.logger.info("\n" + "="*80)
            self.logger.info("PHASE 3: CONTENT SCORING")
            self.logger.info("="*80)

            scoring_result = self.run_phase_script('scripts/run_scoring.py', audio_result)

            if not scoring_result.get('success'):
                self.logger.error(f"Scoring phase failed: {scoring_result.get('error')}")
                return self._log_failure(start_time, "Scoring phase failed")

            episodes_scored = scoring_result.get('episodes_scored', 0)
            self.logger.info(f"📊 Episodes scored: {episodes_scored}")

            if self.phase_stop == 'scoring':
                self.logger.info("Stopping after scoring phase as requested")
                return

            # Phase 4: Digest Generation
            self.logger.info("\n" + "="*80)
            self.logger.info("PHASE 4: DIGEST GENERATION")
            self.logger.info("="*80)

            digest_result = self.run_phase_script('scripts/run_digest.py')

            if not digest_result.get('success'):
                self.logger.error(f"Digest phase failed: {digest_result.get('error')}")
                return self._log_failure(start_time, "Digest phase failed")

            digests_generated = digest_result.get('digests_generated', 0)
            self.logger.info(f"📝 Digests generated: {digests_generated}")

            if self.phase_stop == 'digest':
                self.logger.info("Stopping after digest phase as requested")
                return

            # Phase 5: TTS Audio Generation
            self.logger.info("\n" + "="*80)
            self.logger.info("PHASE 5: TTS AUDIO GENERATION")
            self.logger.info("="*80)

            tts_result = self.run_phase_script('scripts/run_tts.py', digest_result)

            if not tts_result.get('success'):
                self.logger.warning(f"TTS phase failed: {tts_result.get('error')}")
                self.logger.info("📡 Continuing to publishing phase to publish any completed digests...")
                audio_generated = 0
            else:
                audio_generated = tts_result.get('audio_generated', 0)
                self.logger.info(f"🎤 Audio files generated: {audio_generated}")

            if self.phase_stop == 'tts':
                self.logger.info("Stopping after TTS phase as requested")
                return

            # Phase 6: Publishing
            self.logger.info("\n" + "="*80)
            self.logger.info("PHASE 6: PUBLISHING")
            self.logger.info("="*80)

            publishing_result = self.run_phase_script('scripts/run_publishing.py')

            if not publishing_result.get('success'):
                self.logger.warning(f"Publishing phase had issues: {publishing_result.get('error')}")
            else:
                self.logger.info(f"📡 Publishing completed successfully")

            # Final summary
            return self._log_success(
                start_time,
                episodes_found,
                scoring_result.get('episodes', []),
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

        # Run retention cleanup using WebConfig settings
        if self.retention_manager:
            try:
                self.logger.info("🧹 Running retention cleanup...")
                cleanup_stats = self.retention_manager.cleanup_all(dry_run=self.dry_run)
                if cleanup_stats.files_deleted > 0 or cleanup_stats.github_releases_deleted > 0:
                    self.logger.info(f"   Cleaned up {cleanup_stats.files_deleted} files, {cleanup_stats.github_releases_deleted} GitHub releases")
                    self.logger.info(f"   Freed {cleanup_stats.bytes_freed / (1024*1024):.1f} MB")
                else:
                    self.logger.info("   No files needed cleanup")
            except Exception as e:
                self.logger.warning(f"⚠️  Retention cleanup failed: {e}")

        self.logger.info(f"\n📋 Log File: {self.log_file}")
        self.logger.info("🚀 Pipeline orchestration completed successfully!")

    def _log_failure(self, start_time, error_message):
        """Log pipeline failure"""

        elapsed = datetime.now() - start_time

        self.logger.error(f"\n💥 PIPELINE FAILED after {elapsed}")
        self.logger.error(f"Error: {error_message}")
        self.logger.error(f"📋 Check log file for details: {self.log_file}")

def main():
    parser = argparse.ArgumentParser(description='Run complete RSS podcast pipeline (orchestrator)')
    parser.add_argument('--log', help='Log file path', default=None)
    parser.add_argument('--phase', help='Stop after phase',
                       choices=['discovery','audio','scoring','digest','tts'], default=None)

    # Enhanced Phase 1 CLI flags
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be processed without making changes')
    parser.add_argument('--limit', type=int, help='Limit number of episodes to process', default=None)
    parser.add_argument('--days-back', type=int, help='Only process episodes from N days back', default=7)
    parser.add_argument('--episode-guid', help='Process specific episode by GUID', default=None)
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')

    args = parser.parse_args()

    orchestrator = PipelineOrchestrator(
        log_file=args.log,
        phase_stop=args.phase,
        dry_run=args.dry_run,
        limit=args.limit,
        days_back=args.days_back,
        episode_guid=args.episode_guid,
        verbose=args.verbose
    )

    orchestrator.run_pipeline()

if __name__ == '__main__':
    main()