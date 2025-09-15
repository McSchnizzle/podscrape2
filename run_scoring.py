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


def main():
    parser = argparse.ArgumentParser(description='Run content scoring phase only')
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
    logger.info("🔧 PHASE SCRIPT: run_scoring.py v1.0 - Independent execution")
    logger.info("🎯 Content Scoring Phase - AI-powered topic relevance scoring")

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

    print("📊 Running Content Scoring Phase...")
    runner.run_pipeline()
    print("✅ Scoring phase complete!")


if __name__ == '__main__':
    main()