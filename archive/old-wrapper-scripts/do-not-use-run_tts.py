#!/usr/bin/env python3
"""
TTS Phase - Text-to-Speech Audio Generation
Part of the modularized pipeline for individual phase execution.
"""

import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from run_full_pipeline import FullPipelineRunner
from pipeline.phase_output import report_phase_result, should_output_json, setup_phase_logging, add_json_output_arg


def main():
    parser = argparse.ArgumentParser(description='Run TTS audio generation phase only')
    parser.add_argument('--log', help='Log file path', default=None)
    parser.add_argument('--dry-run', action='store_true', help='Show what would be processed without making changes')
    parser.add_argument('--limit', type=int, help='Limit number of episodes to process', default=None)
    parser.add_argument('--days-back', type=int, help='Only process episodes from N days back', default=7)
    parser.add_argument('--episode-guid', help='Process specific episode by GUID', default=None)
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')

    # Add JSON output support
    add_json_output_arg(parser)

    args = parser.parse_args()

    # Setup phase logging (goes to stderr, not stdout)
    logger = setup_phase_logging('tts')

    try:
        # Create runner with TTS phase stop
        runner = FullPipelineRunner(
            log_file=args.log,
            phase_stop='tts',  # Stop after TTS generation
            dry_run=args.dry_run,
            limit=args.limit,
            days_back=args.days_back,
            episode_guid=args.episode_guid,
            verbose=args.verbose
        )

        logger.info("🎤 Running TTS Audio Generation Phase...")
        audio_count = runner.run_pipeline()
        logger.info("✅ TTS phase complete!")

        # Capture audio count from runner - handle cases where run_pipeline returns None
        if audio_count is None:
            # If run_pipeline doesn't return count, fallback to 0
            audio_count = 0

        # Report result using unified function
        exit_code = report_phase_result(
            phase_name='tts',
            success=True,
            metadata={'audio_files_generated': audio_count},
            json_mode=should_output_json(args)
        )

        sys.exit(exit_code)

    except Exception as e:
        logger.error(f"TTS phase failed: {e}")

        # Report error using unified function
        exit_code = report_phase_result(
            phase_name='tts',
            success=False,
            error=str(e),
            json_mode=should_output_json(args)
        )

        sys.exit(exit_code)


if __name__ == '__main__':
    main()