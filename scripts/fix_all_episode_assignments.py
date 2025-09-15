#!/usr/bin/env python3
"""
Comprehensive fix for all episode assignment issues identified by user.
This script handles:
1. Episodes assigned to wrong feeds based on audio URL patterns
2. Duplicate episodes that need cleanup
3. Specific episodes mentioned by user
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from config.env import require_database_url
from sqlalchemy import create_engine, text
from dotenv import load_dotenv


def fix_all_episode_assignments():
    """Fix all episode assignment issues comprehensively."""

    load_dotenv()
    db_url = require_database_url()
    engine = create_engine(db_url)

    print('Comprehensive Episode Assignment Fix')
    print('=' * 60)

    with engine.connect() as conn:
        # Step 1: Handle duplicate episodes
        print("Step 1: Checking for duplicate episodes...")
        print("-" * 40)

        duplicates = conn.execute(text('''
            SELECT e.title, COUNT(*) as count,
                   array_agg(e.id ORDER BY e.id) as episode_ids,
                   array_agg(f.title ORDER BY e.id) as feed_names,
                   array_agg(e.published_date ORDER BY e.id) as published_dates
            FROM episodes e
            JOIN feeds f ON e.feed_id = f.id
            GROUP BY e.title
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        ''')).fetchall()

        for dup in duplicates:
            print(f"Duplicate: {dup.title}")
            print(f"  Episode IDs: {dup.episode_ids}")
            print(f"  Feeds: {dup.feed_names}")
            print(f"  Dates: {dup.published_dates}")
            print()

        # Step 2: Fix episodes based on audio URL patterns (anchor.fm)
        print("Step 2: Fixing episodes based on audio URL patterns...")
        print("-" * 40)

        # Get all anchor.fm episodes and their show IDs
        anchor_episodes = conn.execute(text('''
            SELECT e.id, e.title, e.episode_guid, e.audio_url,
                   f.id as current_feed_id, f.title as current_feed,
                   CASE
                       WHEN e.audio_url LIKE '%anchor.fm/s/%' THEN
                           split_part(split_part(e.audio_url, 'anchor.fm/s/', 2), '/', 1)
                       ELSE NULL
                   END as audio_show_id
            FROM episodes e
            JOIN feeds f ON e.feed_id = f.id
            WHERE e.audio_url LIKE '%anchor.fm/s/%'
        ''')).fetchall()

        # Get anchor.fm feed mappings
        anchor_feeds = conn.execute(text('''
            SELECT id, title, feed_url,
                   split_part(split_part(feed_url, 'anchor.fm/s/', 2), '/', 1) as feed_show_id
            FROM feeds
            WHERE feed_url LIKE '%anchor.fm/s/%'
        ''')).fetchall()

        # Create mapping
        show_id_to_feed = {}
        for feed in anchor_feeds:
            show_id_to_feed[feed.feed_show_id] = {
                'id': feed.id,
                'title': feed.title
            }

        print("Anchor.fm show ID mappings:")
        for show_id, feed_info in show_id_to_feed.items():
            print(f"  {show_id} → {feed_info['title']} (ID: {feed_info['id']})")
        print()

        # Find and fix misassigned episodes
        fixes_applied = 0
        for episode in anchor_episodes:
            if episode.audio_show_id and episode.audio_show_id in show_id_to_feed:
                correct_feed = show_id_to_feed[episode.audio_show_id]
                if correct_feed['id'] != episode.current_feed_id:
                    print(f"Fixing: {episode.title[:50]}...")
                    print(f"  From: {episode.current_feed} (ID: {episode.current_feed_id})")
                    print(f"  To: {correct_feed['title']} (ID: {correct_feed['id']})")
                    print(f"  Show ID: {episode.audio_show_id}")

                    # Update the episode
                    result = conn.execute(text('''
                        UPDATE episodes
                        SET feed_id = :correct_feed_id, updated_at = NOW()
                        WHERE id = :episode_id
                    '''), {
                        'correct_feed_id': correct_feed['id'],
                        'episode_id': episode.id
                    })

                    if result.rowcount > 0:
                        fixes_applied += 1
                        print(f"  ✅ Fixed!")
                    else:
                        print(f"  ❌ Failed to update")
                    print()

        # Step 3: Handle specific user-reported issues
        print("Step 3: Handling specific user-reported episodes...")
        print("-" * 40)

        # Already handled by audio URL pattern matching above, but let's verify
        specific_checks = [
            {
                'title_pattern': '%meeting notes%prototypes%',
                'expected_feed': 'How I AI',
                'show_id': '1035b1568'
            },
            {
                'title_pattern': '%SECURITY CULTURE 101%',
                'expected_feed': 'The Dugout',
                'show_id': 'e8e55a68'
            }
        ]

        for check in specific_checks:
            verification = conn.execute(text('''
                SELECT e.id, e.title, f.title as current_feed
                FROM episodes e
                JOIN feeds f ON e.feed_id = f.id
                WHERE e.title LIKE :pattern
            '''), {'pattern': check['title_pattern']}).fetchall()

            for ep in verification:
                if ep.current_feed == check['expected_feed']:
                    print(f"✅ Verified: '{ep.title[:50]}...' is correctly in {ep.current_feed}")
                else:
                    print(f"⚠️  Still incorrect: '{ep.title[:50]}...' is in {ep.current_feed}, should be {check['expected_feed']}")

        # Commit all changes
        conn.commit()

        # Step 4: Update feed last_episode_date for affected feeds
        print("\nStep 4: Updating feed last_episode_date values...")
        print("-" * 40)

        # Get all unique feed IDs that might have been affected
        all_feed_ids = conn.execute(text('SELECT DISTINCT id FROM feeds')).fetchall()

        for feed_row in all_feed_ids:
            feed_id = feed_row.id
            latest_result = conn.execute(text('''
                SELECT MAX(published_date) as latest_date
                FROM episodes
                WHERE feed_id = :feed_id
            '''), {'feed_id': feed_id}).fetchone()

            latest_date = latest_result.latest_date if latest_result else None

            if latest_date:
                conn.execute(text('''
                    UPDATE feeds
                    SET last_episode_date = :latest_date, updated_at = NOW()
                    WHERE id = :feed_id
                '''), {'latest_date': latest_date, 'feed_id': feed_id})
            else:
                conn.execute(text('''
                    UPDATE feeds
                    SET last_episode_date = NULL, updated_at = NOW()
                    WHERE id = :feed_id
                '''), {'feed_id': feed_id})

        conn.commit()

        print(f"✅ Applied {fixes_applied} episode assignment fixes")
        print("✅ Updated all feed last_episode_date values")

        # Step 5: Final verification
        print("\nStep 5: Final verification...")
        print("-" * 40)

        # Check for any remaining anchor.fm mismatches
        remaining_issues = conn.execute(text('''
            SELECT COUNT(*) as count
            FROM episodes e
            JOIN feeds f ON e.feed_id = f.id
            WHERE e.audio_url LIKE '%anchor.fm/s/%'
              AND NOT EXISTS (
                  SELECT 1 FROM feeds f2
                  WHERE f2.id = e.feed_id
                    AND f2.feed_url LIKE '%anchor.fm/s/%'
                    AND split_part(split_part(e.audio_url, 'anchor.fm/s/', 2), '/', 1) =
                        split_part(split_part(f2.feed_url, 'anchor.fm/s/', 2), '/', 1)
              )
        ''')).scalar()

        if remaining_issues == 0:
            print("✅ All anchor.fm episodes are now correctly assigned!")
        else:
            print(f"⚠️  {remaining_issues} anchor.fm episodes still have mismatched assignments")


if __name__ == "__main__":
    fix_all_episode_assignments()