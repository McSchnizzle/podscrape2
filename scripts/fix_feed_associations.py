#!/usr/bin/env python3
"""
Fix feed-episode associations by updating last_episode_date in feeds table.
Updates each feed's last_episode_date to match the actual latest episode.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from config.env import require_database_url
from sqlalchemy import create_engine, text
from dotenv import load_dotenv


def fix_feed_associations():
    """Fix feed-episode associations by updating last_episode_date."""

    load_dotenv()
    db_url = require_database_url()
    engine = create_engine(db_url)

    print('Fixing feed-episode associations...\n')

    with engine.connect() as conn:
        # First, get all feeds with their actual latest episode dates
        result = conn.execute(text('''
            SELECT f.id, f.title, f.last_episode_date,
                   MAX(e.published_date) as actual_latest_episode
            FROM feeds f
            INNER JOIN episodes e ON f.id = e.feed_id
            GROUP BY f.id, f.title, f.last_episode_date
            HAVING MAX(e.published_date) IS NOT NULL
        '''))

        all_feeds = list(result)

        # Filter feeds that actually need fixing
        feeds_to_fix = []
        for row in all_feeds:
            stored_date = row.last_episode_date
            actual_date = row.actual_latest_episode

            # Check if they need fixing
            needs_fix = False
            if stored_date is None and actual_date is not None:
                needs_fix = True
            elif stored_date is not None and actual_date is not None:
                # Compare dates (convert to strings for comparison)
                stored_str = str(stored_date)[:10]
                actual_str = str(actual_date)[:10]
                if stored_str != actual_str:
                    needs_fix = True

            if needs_fix:
                feeds_to_fix.append(row)

        if not feeds_to_fix:
            print("✅ No feeds need fixing - all associations are correct!")
            return

        print(f"Found {len(feeds_to_fix)} feeds to fix:\n")

        # Update each feed's last_episode_date
        fixed_count = 0
        for row in feeds_to_fix:
            feed_id = row.id
            title = row.title
            latest_episode = row.actual_latest_episode

            print(f"Fixing Feed {feed_id}: {title[:50]}...")
            print(f"  Setting last_episode_date to: {latest_episode}")

            # Update the feed
            update_result = conn.execute(text('''
                UPDATE feeds
                SET last_episode_date = :latest_date,
                    updated_at = NOW()
                WHERE id = :feed_id
            '''), {
                'latest_date': latest_episode,
                'feed_id': feed_id
            })

            if update_result.rowcount > 0:
                fixed_count += 1
                print(f"  ✅ Updated successfully")
            else:
                print(f"  ❌ Update failed")
            print()

        # Commit all changes
        conn.commit()

        print(f"✅ Fixed {fixed_count} out of {len(feeds_to_fix)} feeds")

        # Verify the fix
        print("\nVerifying fixes...")
        verification_result = conn.execute(text('''
            SELECT COUNT(*) as remaining_mismatches
            FROM feeds f
            LEFT JOIN (
                SELECT feed_id, MAX(published_date) as max_date
                FROM episodes
                GROUP BY feed_id
            ) e ON f.id = e.feed_id
            WHERE (f.last_episode_date IS NULL AND e.max_date IS NOT NULL)
               OR (f.last_episode_date IS NOT NULL AND e.max_date IS NULL)
               OR (f.last_episode_date != e.max_date)
        '''))

        remaining = verification_result.scalar()
        if remaining == 0:
            print("✅ All feed associations are now correct!")
        else:
            print(f"⚠️  {remaining} mismatches still remain")


if __name__ == "__main__":
    fix_feed_associations()