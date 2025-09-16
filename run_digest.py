#!/usr/bin/env python3
"""
Digest Generation Phase - Script Creation for Qualifying Topics
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
    parser = argparse.ArgumentParser(description='Run digest generation phase only')
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
    logger = setup_phase_logging('digest')

    try:
        # Create runner with digest phase stop
        runner = FullPipelineRunner(
            log_file=args.log,
            phase_stop='digest',  # Stop after digest generation
            dry_run=args.dry_run,
            limit=args.limit,
            days_back=args.days_back,
            episode_guid=args.episode_guid,
            verbose=args.verbose
        )

        logger.info("📝 Running Digest Generation Phase...")
        digest_count = runner.run_pipeline()
        logger.info("✅ Digest generation phase complete!")

        # Capture digest count from runner - handle cases where run_pipeline returns None
        if digest_count is None:
            # If run_pipeline doesn't return count, fallback to 0
            digest_count = 0

        # Report result using unified function
        exit_code = report_phase_result(
            phase_name='digest',
            success=True,
            metadata={'digests_generated': digest_count},
            json_mode=should_output_json(args)
        )

        sys.exit(exit_code)

    except Exception as e:
        logger.error(f"Digest generation phase failed: {e}")

        # Report error using unified function
        exit_code = report_phase_result(
            phase_name='digest',
            success=False,
            error=str(e),
            json_mode=should_output_json(args)
        )

        sys.exit(exit_code)


if __name__ == '__main__':
    main()