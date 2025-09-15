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

class PipelineOrchestrator:
    """
    Orchestrates the complete pipeline by calling individual phase scripts
    """

    def __init__(self, log_file: str = None, phase_stop: str = None, dry_run: bool = False,
                 limit: int = None, days_back: int = 7, episode_guid: str = None, verbose: bool = False):

        # Set up logging
        if log_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = f"pipeline_orchestrator_{timestamp}.log"

        # Configure logging to both console and file
        handlers = [logging.FileHandler(log_file)]
        try:
            if sys.stdout.isatty():
                handlers.append(logging.StreamHandler(sys.stdout))
        except Exception:
            pass

        logging.basicConfig(
            level=logging.DEBUG if verbose else logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=handlers
        )

        self.logger = logging.getLogger(__name__)

        # Store configuration
        self.log_file = log_file
        self.phase_stop = phase_stop
        self.dry_run = dry_run
        self.limit = limit
        self.days_back = days_back
        self.episode_guid = episode_guid
        self.verbose = verbose

        # Script paths
        self.scripts_dir = Path(__file__).parent / 'scripts'

        self.logger.info("="*100)
        self.logger.info("FULL RSS PODCAST PIPELINE ORCHESTRATOR")
        self.logger.info("="*100)
        self.logger.info(f"Logging to: {log_file}")

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

    def run_phase_script(self, script_name: str, input_data=None, **kwargs):
        """Run a phase script and return the result"""

        script_path = self.scripts_dir / script_name
        if not script_path.exists():
            raise FileNotFoundError(f"Phase script not found: {script_path}")

        # Build command
        cmd = ['python3', str(script_path)]

        # Add common flags
        if self.dry_run:
            cmd.append('--dry-run')
        if self.limit and script_name != 'run_discovery.py':  # Discovery has its own limit handling
            cmd.extend(['--limit', str(self.limit)])
        if self.verbose:
            cmd.append('--verbose')

        # Add script-specific flags
        if script_name == 'run_discovery.py':
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
                input_json = json.dumps(input_data).encode('utf-8')

            # Run the script
            result = subprocess.run(
                cmd,
                input=input_json,
                capture_output=True,
                text=True,
                timeout=1800  # 30 minute timeout
            )

            # Parse output
            if result.returncode == 0:
                try:
                    output_data = json.loads(result.stdout)
                    self.logger.info(f"✅ Phase completed successfully")
                    return output_data
                except json.JSONDecodeError:
                    self.logger.error(f"Invalid JSON output from {script_name}")
                    self.logger.error(f"stdout: {result.stdout}")
                    self.logger.error(f"stderr: {result.stderr}")
                    return {'success': False, 'error': 'Invalid JSON output'}
            else:
                self.logger.error(f"❌ Phase failed with exit code {result.returncode}")
                self.logger.error(f"stderr: {result.stderr}")
                if result.stdout:
                    try:
                        error_data = json.loads(result.stdout)
                        return error_data
                    except json.JSONDecodeError:
                        pass
                return {'success': False, 'error': f'Script failed: {result.stderr}'}

        except subprocess.TimeoutExpired:
            self.logger.error(f"❌ Phase timed out after 30 minutes")
            return {'success': False, 'error': 'Script timed out'}
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

            discovery_result = self.run_phase_script('run_discovery.py')

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

            audio_result = self.run_phase_script('run_audio.py', discovery_result)

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

            scoring_result = self.run_phase_script('run_scoring.py', audio_result)

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

            digest_result = self.run_phase_script('run_digest.py', scoring_result)

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

            tts_result = self.run_phase_script('run_tts.py', digest_result)

            if not tts_result.get('success'):
                self.logger.error(f"TTS phase failed: {tts_result.get('error')}")
                return self._log_failure(start_time, "TTS phase failed")

            audio_generated = tts_result.get('audio_generated', 0)
            self.logger.info(f"🎤 Audio files generated: {audio_generated}")

            if self.phase_stop == 'tts':
                self.logger.info("Stopping after TTS phase as requested")
                return

            # Phase 6: Publishing
            self.logger.info("\n" + "="*80)
            self.logger.info("PHASE 6: PUBLISHING")
            self.logger.info("="*80)

            publishing_result = self.run_phase_script('run_publishing.py')

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
                tts_result.get('audio_results', [])
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