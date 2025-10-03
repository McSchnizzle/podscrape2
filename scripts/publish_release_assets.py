#!/usr/bin/env python3
"""
GitHub Release Assets Publisher for RSS Podcast Digest System

This script provides a CLI interface to the GitHubPublisher class for:
- Publishing MP3 files to GitHub Releases with proper Content-Type: audio/mpeg
- Managing release retention (delete releases older than 7 days by default)
- Creating daily releases with proper metadata

Phase 2 implementation for move-online plan.
"""

import sys
import os
import argparse
import logging
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config.env import load_env
from src.publishing.github_publisher import create_github_publisher, GitHubPublisher
from src.publishing.retention_manager import create_retention_manager
from src.utils.logging_config import get_logger
from src.utils.timezone import get_pacific_now

logger = get_logger(__name__)


def find_mp3_files(search_paths: List[str]) -> List[str]:
    """
    Find all MP3 files in the specified paths

    Args:
        search_paths: List of directories or files to search

    Returns:
        List of MP3 file paths
    """
    mp3_files = []

    for search_path in search_paths:
        path = Path(search_path)

        if not path.exists():
            logger.warning(f"Path does not exist: {path}")
            continue

        if path.is_file() and path.suffix.lower() == '.mp3':
            mp3_files.append(str(path))
        elif path.is_dir():
            # Find all MP3 files in directory
            for mp3_file in path.rglob('*.mp3'):
                mp3_files.append(str(mp3_file))

    return mp3_files


def publish_daily_release(publisher: GitHubPublisher, release_date: date,
                         mp3_paths: List[str]) -> bool:
    """
    Publish MP3 files as a daily GitHub release

    Args:
        publisher: GitHubPublisher instance
        release_date: Date for the release
        mp3_paths: List of MP3 file paths

    Returns:
        True if successful, False otherwise
    """
    try:
        if not mp3_paths:
            logger.error("No MP3 files provided for publishing")
            return False

        logger.info(f"Publishing {len(mp3_paths)} MP3 files for {release_date}")

        # Validate files exist
        valid_files = []
        for mp3_path in mp3_paths:
            if Path(mp3_path).exists():
                valid_files.append(mp3_path)
            else:
                logger.warning(f"File not found: {mp3_path}")

        if not valid_files:
            logger.error("No valid MP3 files found")
            return False

        # Create release
        release = publisher.create_daily_release(release_date, valid_files)

        logger.info(f"✅ Successfully published release: {release.name}")
        logger.info(f"   Release ID: {release.id}")
        logger.info(f"   Assets: {len(release.assets)}")
        logger.info(f"   URL: {release.html_url}")

        return True

    except Exception as e:
        logger.error(f"Failed to publish daily release: {e}")
        return False


def cleanup_old_releases(publisher: GitHubPublisher, keep_days: int = 7) -> bool:
    """
    Clean up GitHub releases older than keep_days

    Args:
        publisher: GitHubPublisher instance
        keep_days: Number of days to keep releases

    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"Cleaning up releases older than {keep_days} days")
        publisher.cleanup_old_releases(keep_days)
        logger.info("✅ Release cleanup completed successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to cleanup releases: {e}")
        return False


def list_recent_releases(publisher: GitHubPublisher, limit: int = 10):
    """
    List recent GitHub releases

    Args:
        publisher: GitHubPublisher instance
        limit: Number of releases to show
    """
    try:
        releases = publisher.list_releases(limit)

        if not releases:
            print("No releases found")
            return

        print(f"\n📋 Recent Releases ({len(releases)}):")
        print("-" * 80)

        for release in releases:
            asset_count = len(release.assets)
            asset_size = sum(asset['size'] for asset in release.assets)

            print(f"• {release.name}")
            print(f"  Tag: {release.tag_name}")
            print(f"  Published: {release.published_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"  Assets: {asset_count} files ({format_bytes(asset_size)})")

            if asset_count > 0:
                print("  Files:")
                for asset in release.assets:
                    print(f"    - {asset['name']} ({format_bytes(asset['size'])})")

            print(f"  URL: {release.html_url}")
            print()

    except Exception as e:
        logger.error(f"Failed to list releases: {e}")


def format_bytes(bytes_count: int) -> str:
    """Format byte count in human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_count < 1024.0:
            return f"{bytes_count:.1f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.1f} TB"


def main():
    parser = argparse.ArgumentParser(
        description='Publish MP3 files to GitHub Releases and manage retention',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Publish all MP3s from data/completed-tts/ for today
  python3 scripts/publish_release_assets.py --publish-today data/completed-tts/

  # Publish specific MP3 files for a specific date
  python3 scripts/publish_release_assets.py --publish-date 2024-01-15 file1.mp3 file2.mp3

  # List recent releases
  python3 scripts/publish_release_assets.py --list-releases

  # Clean up releases older than 7 days
  python3 scripts/publish_release_assets.py --cleanup --keep-days 7

  # Publish all current MP3s and cleanup old releases
  python3 scripts/publish_release_assets.py --publish-today data/completed-tts/ --cleanup
        """
    )

    # Main actions
    parser.add_argument('--publish-today', metavar='PATH', nargs='*',
                       help='Publish MP3 files for today\'s date from specified paths')
    parser.add_argument('--publish-date', metavar='YYYY-MM-DD',
                       help='Publish MP3 files for specific date (use with positional MP3 files)')
    parser.add_argument('--list-releases', action='store_true',
                       help='List recent GitHub releases')
    parser.add_argument('--cleanup', action='store_true',
                       help='Clean up old releases')

    # Options
    parser.add_argument('--keep-days', type=int, default=7,
                       help='Number of days to keep releases (default: 7)')
    parser.add_argument('--limit', type=int, default=10,
                       help='Number of releases to show (default: 10)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose logging')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without actually doing it')

    # Positional arguments for MP3 files
    parser.add_argument('mp3_files', nargs='*',
                       help='MP3 files to publish (used with --publish-date)')

    args = parser.parse_args()

    # Configure logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)

    # Load environment
    load_env()

    try:
        # Initialize publisher
        publisher = create_github_publisher()
        success = True

        # Handle publish-today
        if args.publish_today is not None:
            search_paths = args.publish_today or ['data/completed-tts/']
            mp3_files = find_mp3_files(search_paths)

            if mp3_files:
                today = get_pacific_now().date()
                if args.dry_run:
                    print(f"Would publish {len(mp3_files)} MP3 files for {today}")
                    for mp3_file in mp3_files:
                        print(f"  - {mp3_file}")
                else:
                    success = publish_daily_release(publisher, today, mp3_files)
            else:
                logger.error(f"No MP3 files found in: {search_paths}")
                success = False

        # Handle publish-date
        elif args.publish_date:
            try:
                release_date = datetime.strptime(args.publish_date, '%Y-%m-%d').date()
                mp3_files = args.mp3_files

                if not mp3_files:
                    logger.error("No MP3 files specified for date publishing")
                    success = False
                else:
                    if args.dry_run:
                        print(f"Would publish {len(mp3_files)} MP3 files for {release_date}")
                        for mp3_file in mp3_files:
                            print(f"  - {mp3_file}")
                    else:
                        success = publish_daily_release(publisher, release_date, mp3_files)

            except ValueError:
                logger.error("Invalid date format. Use YYYY-MM-DD")
                success = False

        # Handle list-releases
        elif args.list_releases:
            list_recent_releases(publisher, args.limit)

        # Handle cleanup
        if args.cleanup:
            if args.dry_run:
                print(f"Would clean up releases older than {args.keep_days} days")
                # Show which releases would be deleted
                releases = publisher.list_releases()
                cutoff_date = get_pacific_now() - timedelta(days=args.keep_days)
                old_releases = [r for r in releases if r.published_at.replace(tzinfo=None) < cutoff_date]

                if old_releases:
                    print(f"Would delete {len(old_releases)} releases:")
                    for release in old_releases:
                        print(f"  - {release.name} ({release.published_at.date()})")
                else:
                    print("No releases to delete")
            else:
                cleanup_success = cleanup_old_releases(publisher, args.keep_days)
                success = success and cleanup_success

        # Default action if no specific command given
        if not any([args.publish_today is not None, args.publish_date,
                   args.list_releases, args.cleanup]):
            parser.print_help()
            return 0

        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n⏹️  Operation cancelled by user")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())