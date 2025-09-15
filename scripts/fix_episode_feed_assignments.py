#!/usr/bin/env python3
"""
Fix incorrect episode-feed assignments caused by ID changes during migration.
Episodes should be associated with feeds based on their audio URL domains and GUIDs.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from config.env import require_database_url
from sqlalchemy import create_engine, text
from dotenv import load_dotenv


def fix_episode_feed_assignments():
    """Fix episode-feed assignments based on audio URL patterns and GUIDs."""

    load_dotenv()
    db_url = require_database_url()
    engine = create_engine(db_url)

    print('Fixing episode-feed assignments...\n')

    with engine.connect() as conn:
        # Find episodes that need to be reassigned based on their audio URLs and GUIDs
        print("Step 1: Identifying misassigned episodes...")

        # Find episodes with bitterlake.podbean.com GUIDs that should belong to "THIS IS REVOLUTION"
        bitterlake_episodes = conn.execute(text('''
            SELECT e.id, e.title, e.feed_id, e.episode_guid, e.audio_url,
                   f.title as current_feed_title, f.feed_url as current_feed_url
            FROM episodes e
            JOIN feeds f ON e.feed_id = f.id
            WHERE e.episode_guid LIKE 'bitterlake.podbean.com%'
        ''')).fetchall()

        # Find the correct feed ID for "THIS IS REVOLUTION"
        correct_feed = conn.execute(text('''
            SELECT id, title, feed_url
            FROM feeds
            WHERE feed_url = 'https://feed.podbean.com/bitterlake/feed.xml'
        ''')).fetchone()

        if not correct_feed:
            print("❌ Could not find 'THIS IS REVOLUTION' feed in database!")
            return

        correct_feed_id = correct_feed.id
        print(f"✅ Found correct feed: '{correct_feed.title}' (ID: {correct_feed_id})")
        print(f"   Feed URL: {correct_feed.feed_url}")

        if not bitterlake_episodes:
            print("✅ No bitterlake episodes found that need fixing!")
            return

        print(f"\nStep 2: Found {len(bitterlake_episodes)} episodes to reassign:")
        print("-" * 80)

        episodes_to_fix = []
        for episode in bitterlake_episodes:
            if episode.feed_id != correct_feed_id:
                episodes_to_fix.append(episode)
                print(f"Episode: {episode.title[:50]}...")
                print(f"  Current Feed: {episode.current_feed_title} (ID: {episode.feed_id})")
                print(f"  Should be: {correct_feed.title} (ID: {correct_feed_id})")
                print(f"  GUID: {episode.episode_guid}")
                print()

        if not episodes_to_fix:
            print("✅ All bitterlake episodes are already correctly assigned!")
            return

        print(f"Step 3: Fixing {len(episodes_to_fix)} episode assignments...")
        print("-" * 80)

        fixed_count = 0
        for episode in episodes_to_fix:
            print(f"Fixing: {episode.title[:50]}...")

            result = conn.execute(text('''
                UPDATE episodes
                SET feed_id = :correct_feed_id, updated_at = NOW()
                WHERE id = :episode_id
            '''), {
                'correct_feed_id': correct_feed_id,
                'episode_id': episode.id
            })

            if result.rowcount > 0:
                fixed_count += 1
                print(f"  ✅ Moved from Feed {episode.feed_id} to Feed {correct_feed_id}")
            else:
                print(f"  ❌ Failed to update")

        # Commit all changes
        conn.commit()

        print(f"\n✅ Successfully fixed {fixed_count} out of {len(episodes_to_fix)} episodes")

        # Update feed last_episode_date for affected feeds
        print("\nStep 4: Updating feed last_episode_date values...")

        affected_feed_ids = set([episode.feed_id for episode in episodes_to_fix] + [correct_feed_id])

        for feed_id in affected_feed_ids:
            latest_result = conn.execute(text('''
                SELECT MAX(published_date) as latest_date
                FROM episodes
                WHERE feed_id = :feed_id
            '''), {'feed_id': feed_id})

            latest_date = latest_result.scalar()

            if latest_date:
                conn.execute(text('''
                    UPDATE feeds
                    SET last_episode_date = :latest_date, updated_at = NOW()
                    WHERE id = :feed_id
                '''), {'latest_date': latest_date, 'feed_id': feed_id})
                print(f"  ✅ Updated Feed {feed_id} last_episode_date to {latest_date}")
            else:
                # No episodes left, clear the last_episode_date
                conn.execute(text('''
                    UPDATE feeds
                    SET last_episode_date = NULL, updated_at = NOW()
                    WHERE id = :feed_id
                '''), {'feed_id': feed_id})
                print(f"  ✅ Cleared Feed {feed_id} last_episode_date (no episodes)")

        conn.commit()

        print("\nStep 5: Verification...")
        # Verify the fix
        verification = conn.execute(text('''
            SELECT COUNT(*) as count
            FROM episodes e
            JOIN feeds f ON e.feed_id = f.id
            WHERE e.episode_guid LIKE 'bitterlake.podbean.com%'
              AND f.feed_url = 'https://feed.podbean.com/bitterlake/feed.xml'
        ''')).scalar()

        total_bitterlake = conn.execute(text('''
            SELECT COUNT(*) as count
            FROM episodes
            WHERE episode_guid LIKE 'bitterlake.podbean.com%'
        ''')).scalar()

        if verification == total_bitterlake:
            print(f"✅ All {total_bitterlake} bitterlake episodes are now correctly assigned!")
        else:
            print(f"⚠️  Only {verification} out of {total_bitterlake} bitterlake episodes are correctly assigned")


if __name__ == "__main__":
    fix_episode_feed_assignments()