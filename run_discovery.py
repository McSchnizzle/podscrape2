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


def main():
    parser = argparse.ArgumentParser(description='Run RSS discovery phase only')
    parser.add_argument('--log', help='Log file path', default=None)
    parser.add_argument('--dry-run', action='store_true', help='Show what would be processed without making changes')
    parser.add_argument('--limit', type=int, help='Limit number of episodes to process', default=None)
    parser.add_argument('--days-back', type=int, help='Only process episodes from N days back', default=7)
    parser.add_argument('--episode-guid', help='Process specific episode by GUID', default=None)
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')

    args = parser.parse_args()

    # Initialize logging with phase identifier
    import logging
    logger = logging.getLogger(__name__)
    logger.info("🔧 PHASE SCRIPT: run_discovery.py v1.0 - Independent execution")
    logger.info("📋 Discovery Phase - RSS Feed Discovery and Episode Identification")

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

    print("🔍 Running RSS Discovery Phase...")
    runner.run_pipeline()
    print("✅ Discovery phase complete!")


if __name__ == '__main__':
    main()