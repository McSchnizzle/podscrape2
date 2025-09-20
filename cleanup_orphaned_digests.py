#!/usr/bin/env python3
"""
Standalone cleanup script to find and clean up orphaned database entries
where mp3_path points to non-existent files.

This script identifies digest records in the database that reference MP3 files
that no longer exist on disk and either removes the records or nullifies the mp3_path.
"""

import os
import logging
import argparse
from pathlib import Path
from typing import List, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from database.models import get_database_manager, get_digest_repo, Digest


def find_orphaned_digests(dry_run: bool = True) -> Tuple[List[Digest], List[Digest]]:
    """
    Find digest records with mp3_path pointing to non-existent files.

    Returns:
        Tuple of (orphaned_digests, valid_digests)
    """
    db_manager = get_database_manager()
    digest_repo = get_digest_repo(db_manager)

    # Get all digests with mp3_path set
    orphaned = []
    valid = []

    logger.info("Checking database for digests with MP3 paths...")

    try:
        # We need to query all digests and check each one
        # Since we don't have a direct "get_all" method, we'll get recent ones going back far
        from datetime import date, timedelta

        # Check last 60 days of digests to catch most orphaned entries
        start_date = date.today() - timedelta(days=60)

        # Get digests by checking each date (this is not ideal but works with current API)
        all_digests = []
        current_date = start_date
        while current_date <= date.today():
            daily_digests = digest_repo.get_by_date(current_date)
            all_digests.extend(daily_digests)
            current_date += timedelta(days=1)

        logger.info(f"Found {len(all_digests)} total digests to check")

        for digest in all_digests:
            if digest.mp3_path:
                mp3_file = Path(digest.mp3_path)
                if mp3_file.exists():
                    valid.append(digest)
                    logger.debug(f"Valid: {digest.topic} - {digest.digest_date} - {mp3_file}")
                else:
                    orphaned.append(digest)
                    logger.info(f"Orphaned: {digest.topic} - {digest.digest_date} - {mp3_file}")

        logger.info(f"Found {len(orphaned)} orphaned digests and {len(valid)} valid digests")
        return orphaned, valid

    except Exception as e:
        logger.error(f"Error finding orphaned digests: {e}")
        raise


def cleanup_orphaned_digests(orphaned_digests: List[Digest], action: str = "nullify", dry_run: bool = True) -> int:
    """
    Clean up orphaned digest records.

    Args:
        orphaned_digests: List of digests with non-existent MP3 files
        action: "nullify" to set mp3_path=NULL, "delete" to delete records
        dry_run: If True, only show what would be done

    Returns:
        Number of records processed
    """
    if not orphaned_digests:
        logger.info("No orphaned digests to clean up")
        return 0

    db_manager = get_database_manager()
    digest_repo = get_digest_repo(db_manager)

    processed = 0

    for digest in orphaned_digests:
        try:
            if action == "nullify":
                if dry_run:
                    logger.info(f"Would nullify mp3_path for digest {digest.id} "
                              f"({digest.topic} - {digest.digest_date})")
                else:
                    # Update digest to remove mp3 info
                    update_data = {
                        'mp3_path': None,
                        'mp3_duration_seconds': None,
                        'mp3_title': None,
                        'mp3_summary': None
                    }
                    digest_repo.update_digest(digest.id, update_data)
                    logger.info(f"Nullified mp3_path for digest {digest.id} "
                              f"({digest.topic} - {digest.digest_date})")

            elif action == "delete":
                if dry_run:
                    logger.info(f"Would delete digest {digest.id} "
                              f"({digest.topic} - {digest.digest_date})")
                else:
                    # Note: We need to add a delete method to DigestRepository
                    # For now, we'll use nullify as the safer option
                    logger.warning(f"Delete not implemented - nullifying instead for digest {digest.id}")
                    update_data = {
                        'mp3_path': None,
                        'mp3_duration_seconds': None,
                        'mp3_title': None,
                        'mp3_summary': None
                    }
                    digest_repo.update_digest(digest.id, update_data)

            processed += 1

        except Exception as e:
            logger.error(f"Failed to process digest {digest.id}: {e}")

    return processed


def main():
    parser = argparse.ArgumentParser(description='Clean up orphaned database digest entries')
    parser.add_argument('--action', choices=['nullify', 'delete'], default='nullify',
                       help='Action to take: nullify mp3_path or delete records (default: nullify)')
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='Show what would be done without actually doing it (default: True)')
    parser.add_argument('--execute', action='store_true',
                       help='Actually execute the cleanup (overrides --dry-run)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose logging')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Determine if this is a dry run
    dry_run = args.dry_run and not args.execute

    if not dry_run:
        response = input("This will modify the database. Are you sure? (y/N): ")
        if response.lower() != 'y':
            logger.info("Cancelled by user")
            return

    logger.info(f"Starting orphaned digest cleanup (dry_run={dry_run}, action={args.action})")

    try:
        # Test database connection
        db_manager = get_database_manager()
        if not db_manager.test_connection():
            logger.error("Database connection failed")
            return 1

        # Find orphaned digests
        orphaned, valid = find_orphaned_digests(dry_run)

        if not orphaned:
            logger.info("✅ No orphaned digests found - database is clean!")
            return 0

        logger.info(f"Found {len(orphaned)} orphaned digests:")
        for digest in orphaned:
            logger.info(f"  • {digest.topic} - {digest.digest_date} - {digest.mp3_path}")

        # Clean up orphaned digests
        processed = cleanup_orphaned_digests(orphaned, args.action, dry_run)

        action_word = "Would process" if dry_run else "Processed"
        logger.info(f"✅ {action_word} {processed} orphaned digest records")

        if dry_run:
            logger.info("Run with --execute to actually perform the cleanup")

        return 0

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())