#!/usr/bin/env python3
"""
Cleanup Released MP3s - One-time cleanup script

Deletes local MP3 files from data/completed-tts/ that:
1. Have been successfully uploaded to GitHub releases (github_url set in database)
2. Are older than the retention period configured in web_settings

This script is safe to run multiple times - it only deletes files that should no longer
be retained locally per the retention policy.
"""

import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Tuple

# Bootstrap
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from src.database.models import get_digest_repo
from src.config.web_config import WebConfigManager
from src.audio.audio_manager import AudioManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def cleanup_released_mp3s(dry_run: bool = True) -> Tuple[int, int, int]:
    """
    Clean up MP3 files that are already released or expired

    Returns:
        Tuple of (released_count, expired_count, bytes_freed)
    """
    logger.info("🧹 Starting cleanup of released MP3 files...")

    # Load retention settings
    try:
        wc = WebConfigManager()
        retention_days = int(wc.get_setting('retention', 'local_mp3_days', 14))
        logger.info(f"Local MP3 retention period: {retention_days} days")
    except Exception as e:
        logger.warning(f"Could not load retention settings, using default 14 days: {e}")
        retention_days = 14

    cutoff_date = datetime.now() - timedelta(days=retention_days)

    # Get all digests with MP3 paths
    digest_repo = get_digest_repo()
    all_digests = digest_repo.get_recent_digests(days=365)  # Get all digests from last year

    released_count = 0
    expired_count = 0
    bytes_freed = 0

    for digest in all_digests:
        if not digest.mp3_path:
            continue

        # Resolve actual file path (handles old 'current/' references)
        mp3_path = AudioManager.resolve_existing_mp3_path(digest.mp3_path)

        # Skip if file doesn't exist
        if not mp3_path:
            continue

        file_size = mp3_path.stat().st_size
        should_delete = False
        reason = ""

        # Check if already released (has github_url)
        if digest.github_url:
            should_delete = True
            reason = "already released to GitHub"
            released_count += 1

        # Check if older than retention period
        elif digest.generated_at and digest.generated_at < cutoff_date:
            should_delete = True
            reason = f"older than {retention_days} days"
            expired_count += 1

        if should_delete:
            if dry_run:
                logger.info(f"  [DRY RUN] Would delete: {mp3_path.name} ({reason})")
            else:
                try:
                    mp3_path.unlink()
                    logger.info(f"  ✅ Deleted: {mp3_path.name} ({reason})")
                except Exception as e:
                    logger.error(f"  ❌ Failed to delete {mp3_path.name}: {e}")
                    continue

            bytes_freed += file_size

    # Summary
    total_deleted = released_count + expired_count
    mb_freed = bytes_freed / (1024 * 1024)

    if dry_run:
        logger.info(f"\n📊 DRY RUN Summary:")
        logger.info(f"  Would delete {total_deleted} MP3 files:")
        logger.info(f"    • {released_count} already released to GitHub")
        logger.info(f"    • {expired_count} older than {retention_days} days")
        logger.info(f"  Would free: {mb_freed:.2f} MB")
        logger.info(f"\n💡 Run with --execute to actually delete files")
    else:
        logger.info(f"\n📊 Cleanup Summary:")
        logger.info(f"  Deleted {total_deleted} MP3 files:")
        logger.info(f"    • {released_count} already released to GitHub")
        logger.info(f"    • {expired_count} older than {retention_days} days")
        logger.info(f"  Freed: {mb_freed:.2f} MB")

    return released_count, expired_count, bytes_freed


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Clean up local MP3 files that are already released or expired',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (default) - see what would be deleted
  python3 scripts/cleanup_released_mp3s.py

  # Actually delete files
  python3 scripts/cleanup_released_mp3s.py --execute
        """
    )
    parser.add_argument('--execute', action='store_true',
                       help='Actually delete files (default is dry run)')

    args = parser.parse_args()

    try:
        released, expired, bytes_freed = cleanup_released_mp3s(dry_run=not args.execute)
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
