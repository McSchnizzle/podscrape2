#!/usr/bin/env python3
"""
Scoring Phase - Content Analysis and Topic Scoring
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
    parser = argparse.ArgumentParser(description='Run content scoring phase only')
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
    logger = setup_phase_logging('scoring')

    try:
        # Create runner with scoring phase stop
        runner = FullPipelineRunner(
            log_file=args.log,
            phase_stop='scoring',  # Stop after scoring
            dry_run=args.dry_run,
            limit=args.limit,
            days_back=args.days_back,
            episode_guid=args.episode_guid,
            verbose=args.verbose
        )

        logger.info("📊 Running Content Scoring Phase...")
        episode_count = runner.run_pipeline()
        logger.info("✅ Scoring phase complete!")

        # Capture episode count from runner - handle cases where run_pipeline returns None
        if episode_count is None:
            # If run_pipeline doesn't return count, get from stored episodes
            episode_count = len(getattr(runner, 'discovered_episodes', []))

        # Report result using unified function
        exit_code = report_phase_result(
            phase_name='scoring',
            success=True,
            metadata={'episodes_scored': episode_count},
            json_mode=should_output_json(args)
        )

        sys.exit(exit_code)

    except Exception as e:
        logger.error(f"Scoring phase failed: {e}")

        # Report error using unified function
        exit_code = report_phase_result(
            phase_name='scoring',
            success=False,
            error=str(e),
            json_mode=should_output_json(args)
        )

        sys.exit(exit_code)


if __name__ == '__main__':
    main()