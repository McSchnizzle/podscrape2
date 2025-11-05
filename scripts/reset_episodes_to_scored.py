#!/usr/bin/env python3
"""
Reset episodes from 'digested' back to 'scored' status.
Use this to re-process episodes after workflow failures.

Usage:
    python3 scripts/reset_episodes_to_scored.py --since 2025-10-31
    python3 scripts/reset_episodes_to_scored.py --since 2025-10-31 --dry-run
"""

import os
import sys
import argparse
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def reset_episodes(cutoff_date: str, dry_run: bool = False):
    """Reset episodes from 'digested' to 'scored' status."""

    # Import psycopg for database operations
    try:
        import psycopg
    except ImportError:
        print("❌ Error: psycopg module not found")
        print("Install with: pip install 'psycopg[binary]'")
        sys.exit(1)

    # Get database URL
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL environment variable not set")
        print("Set it with: export DATABASE_URL='your_connection_string'")
        sys.exit(1)

    print(f"🔍 Connecting to database...")
    print(f"   Cutoff date: {cutoff_date}")
    print(f"   Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}")
    print()

    try:
        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cur:
                # First, check how many episodes match
                check_query = """
                    SELECT COUNT(*) as count
                    FROM episodes
                    WHERE status = 'digested'
                    AND updated_at >= %s
                """

                cur.execute(check_query, (cutoff_date,))
                count = cur.fetchone()[0]

                print(f"📊 Found {count} episodes marked as 'digested' since {cutoff_date}")

                if count == 0:
                    print("✅ No episodes to reset")
                    return 0

                # Show details about what we're resetting
                detail_query = """
                    SELECT id, title, status, updated_at, scores
                    FROM episodes
                    WHERE status = 'digested'
                    AND updated_at >= %s
                    ORDER BY updated_at DESC
                    LIMIT 20
                """

                cur.execute(detail_query, (cutoff_date,))
                episodes = cur.fetchall()

                print(f"\n📋 Episodes to reset (showing up to 20):")
                for ep in episodes:
                    ep_id, title, status, updated, scores = ep
                    # Extract highest score if available
                    max_score = ""
                    if scores and isinstance(scores, dict):
                        max_score = f" [max score: {max(scores.values()):.2f}]" if scores else ""
                    print(f"   ID {ep_id}: {title[:60]}...{max_score}")
                    print(f"      Updated: {updated}")

                if count > 20:
                    print(f"   ... and {count - 20} more episodes")

                if dry_run:
                    print(f"\n🔍 DRY RUN: Would reset {count} episodes from 'digested' to 'scored'")
                    print("   Run without --dry-run to perform the update")
                    return count

                # Perform the update
                print(f"\n🔄 Resetting {count} episodes from 'digested' to 'scored'...")

                update_query = """
                    UPDATE episodes
                    SET status = 'scored',
                        updated_at = NOW()
                    WHERE status = 'digested'
                    AND updated_at >= %s
                """

                cur.execute(update_query, (cutoff_date,))
                updated_count = cur.rowcount
                conn.commit()

                print(f"✅ Successfully reset {updated_count} episodes to 'scored' status")

                # Verify the update
                verify_query = """
                    SELECT COUNT(*) as count
                    FROM episodes
                    WHERE status = 'digested'
                    AND updated_at >= %s
                """

                cur.execute(verify_query, (cutoff_date,))
                remaining = cur.fetchone()[0]

                if remaining == 0:
                    print(f"✅ Verification: No 'digested' episodes remain since {cutoff_date}")
                else:
                    print(f"⚠️  Warning: {remaining} 'digested' episodes still found")

                # Show status distribution
                status_query = """
                    SELECT status, COUNT(*) as count
                    FROM episodes
                    GROUP BY status
                    ORDER BY count DESC
                """

                cur.execute(status_query)
                statuses = cur.fetchall()

                print(f"\n📊 Current episode status distribution:")
                for status, count_val in statuses:
                    print(f"   {status}: {count_val}")

                return updated_count

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description='Reset episodes from digested back to scored status'
    )
    parser.add_argument(
        '--since',
        required=True,
        help='Reset episodes updated since this date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be reset without making changes'
    )

    args = parser.parse_args()

    # Validate date format
    try:
        datetime.strptime(args.since, '%Y-%m-%d')
        cutoff_date = f"{args.since} 00:00:00"
    except ValueError:
        print(f"❌ Invalid date format: {args.since}")
        print("   Expected format: YYYY-MM-DD (e.g., 2025-10-31)")
        sys.exit(1)

    print("=" * 60)
    print("Episode Status Reset Tool")
    print("=" * 60)
    print()

    count = reset_episodes(cutoff_date, args.dry_run)

    print()
    print("=" * 60)
    if args.dry_run:
        print(f"✅ Dry run complete: {count} episodes would be reset")
    else:
        print(f"✅ Reset complete: {count} episodes updated to 'scored' status")
        print("   These episodes will be picked up in the next workflow run")
    print("=" * 60)

if __name__ == '__main__':
    main()
