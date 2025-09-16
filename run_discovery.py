#!/usr/bin/env python3
"""
Discovery Phase - RSS Feed Discovery and Episode Identification
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
    parser = argparse.ArgumentParser(description='Run RSS discovery phase only')
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
    logger = setup_phase_logging('discovery')

    try:
        # Create runner with discovery phase stop
        runner = FullPipelineRunner(
            log_file=args.log,
            phase_stop='discovery',  # Stop after discovery
            dry_run=args.dry_run,
            limit=args.limit,
            days_back=args.days_back,
            episode_guid=args.episode_guid,
            verbose=args.verbose
        )

        logger.info("🔍 Running RSS Discovery Phase...")
        episode_count = runner.run_pipeline()
        logger.info("✅ Discovery phase complete!")

        # Capture episode count from runner - handle cases where run_pipeline returns None
        if episode_count is None:
            # If run_pipeline doesn't return count, get from stored episodes
            episode_count = len(getattr(runner, 'discovered_episodes', []))

        # Report result using unified function
        exit_code = report_phase_result(
            phase_name='discovery',
            success=True,
            metadata={'episodes_found': episode_count},
            json_mode=should_output_json(args)
        )

        sys.exit(exit_code)

    except Exception as e:
        logger.error(f"Discovery phase failed: {e}")

        # Report error using unified function
        exit_code = report_phase_result(
            phase_name='discovery',
            success=False,
            error=str(e),
            json_mode=should_output_json(args)
        )

        sys.exit(exit_code)


if __name__ == '__main__':
    main()