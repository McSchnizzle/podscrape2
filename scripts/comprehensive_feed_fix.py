#!/usr/bin/env python3
"""
Comprehensive fix for episode-feed assignment issues caused by migration.
This script maps episodes to the correct feeds by comparing audio URL patterns,
episode GUIDs, and feed URLs between SQLite and Supabase data.
"""

import sys
import sqlite3
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from config.env import require_database_url
from sqlalchemy import create_engine, text
from dotenv import load_dotenv


def analyze_migration_issues():
    """Analyze the differences between SQLite and Supabase episode-feed assignments."""

    load_dotenv()
    db_url = require_database_url()
    pg_engine = create_engine(db_url)

    # Connect to both databases
    sqlite_path = Path(__file__).parent.parent / "data" / "database" / "_digest.db"
    sqlite_conn = sqlite3.connect(str(sqlite_path))
    sqlite_conn.row_factory = sqlite3.Row

    print('Analyzing migration issues between SQLite and Supabase...\n')

    # Step 1: Get feed mappings from both databases
    print("Step 1: Comparing feed mappings...")
    print("-" * 80)

    # SQLite feeds
    sqlite_feeds = {}
    sqlite_cursor = sqlite_conn.execute("SELECT id, title, feed_url FROM feeds ORDER BY id")
    for row in sqlite_cursor:
        sqlite_feeds[row['feed_url']] = {
            'id': row['id'],
            'title': row['title'],
            'feed_url': row['feed_url']
        }

    print(f"SQLite has {len(sqlite_feeds)} feeds")

    # Supabase feeds
    supabase_feeds = {}
    with pg_engine.connect() as conn:
        result = conn.execute(text("SELECT id, title, feed_url FROM feeds ORDER BY id"))
        for row in result:
            supabase_feeds[row.feed_url] = {
                'id': row.id,
                'title': row.title,
                'feed_url': row.feed_url
            }

    print(f"Supabase has {len(supabase_feeds)} feeds\n")

    # Step 2: Find episodes with mismatched feed assignments
    print("Step 2: Finding episodes with incorrect feed assignments...")
    print("-" * 80)

    misassigned_episodes = []

    # Get all episodes from SQLite
    sqlite_cursor = sqlite_conn.execute("""
        SELECT e.id, e.episode_guid, e.title, e.feed_id, e.audio_url,
               f.feed_url, f.title as feed_title
        FROM episodes e
        JOIN feeds f ON e.feed_id = f.id
    """)

    for sqlite_episode in sqlite_cursor:
        # Find the corresponding feed in Supabase based on feed_url
        sqlite_feed_url = sqlite_episode['feed_url']
        if sqlite_feed_url not in supabase_feeds:
            print(f"⚠️  Feed URL not found in Supabase: {sqlite_feed_url}")
            continue

        correct_supabase_feed_id = supabase_feeds[sqlite_feed_url]['id']

        # Check what feed this episode is currently assigned to in Supabase
        with pg_engine.connect() as conn:
            current_assignment = conn.execute(text("""
                SELECT e.feed_id, f.title as feed_title, f.feed_url
                FROM episodes e
                JOIN feeds f ON e.feed_id = f.id
                WHERE e.episode_guid = :guid
            """), {'guid': sqlite_episode['episode_guid']}).fetchone()

            if current_assignment:
                if current_assignment.feed_id != correct_supabase_feed_id:
                    misassigned_episodes.append({
                        'episode_guid': sqlite_episode['episode_guid'],
                        'episode_title': sqlite_episode['title'],
                        'current_feed_id': current_assignment.feed_id,
                        'current_feed_title': current_assignment.feed_title,
                        'correct_feed_id': correct_supabase_feed_id,
                        'correct_feed_title': supabase_feeds[sqlite_feed_url]['title'],
                        'sqlite_feed_url': sqlite_feed_url
                    })

    print(f"Found {len(misassigned_episodes)} episodes with incorrect feed assignments\n")

    if not misassigned_episodes:
        print("✅ All episodes are correctly assigned!")
        sqlite_conn.close()
        return

    # Step 3: Group misassignments by pattern
    print("Step 3: Analyzing patterns...")
    print("-" * 80)

    by_correct_feed = {}
    by_wrong_feed = {}

    for episode in misassigned_episodes:
        correct_title = episode['correct_feed_title']
        wrong_title = episode['current_feed_title']

        if correct_title not in by_correct_feed:
            by_correct_feed[correct_title] = []
        by_correct_feed[correct_title].append(episode)

        if wrong_title not in by_wrong_feed:
            by_wrong_feed[wrong_title] = []
        by_wrong_feed[wrong_title].append(episode)

    print("Episodes that should belong to:")
    for feed_title, episodes in by_correct_feed.items():
        print(f"  {feed_title}: {len(episodes)} episodes")

    print("\nEpisodes currently incorrectly assigned to:")
    for feed_title, episodes in by_wrong_feed.items():
        print(f"  {feed_title}: {len(episodes)} episodes")

    print(f"\nStep 4: Showing first 10 misassignments for review...")
    print("-" * 80)

    for i, episode in enumerate(misassigned_episodes[:10]):
        print(f"{i+1}. {episode['episode_title'][:50]}...")
        print(f"   Currently: {episode['current_feed_title']} (ID: {episode['current_feed_id']})")
        print(f"   Should be: {episode['correct_feed_title']} (ID: {episode['correct_feed_id']})")
        print()

    if len(misassigned_episodes) > 10:
        print(f"... and {len(misassigned_episodes) - 10} more")

    sqlite_conn.close()
    return misassigned_episodes


def fix_all_assignments(misassigned_episodes):
    """Fix all the misassigned episodes."""

    if not misassigned_episodes:
        print("No episodes to fix!")
        return

    load_dotenv()
    db_url = require_database_url()
    engine = create_engine(db_url)

    print(f"\nFixing {len(misassigned_episodes)} misassigned episodes...")
    print("-" * 80)

    fixed_count = 0
    affected_feeds = set()

    with engine.connect() as conn:
        for episode in misassigned_episodes:
            result = conn.execute(text("""
                UPDATE episodes
                SET feed_id = :correct_feed_id, updated_at = NOW()
                WHERE episode_guid = :episode_guid
            """), {
                'correct_feed_id': episode['correct_feed_id'],
                'episode_guid': episode['episode_guid']
            })

            if result.rowcount > 0:
                fixed_count += 1
                affected_feeds.add(episode['current_feed_id'])
                affected_feeds.add(episode['correct_feed_id'])

                if fixed_count <= 5:  # Show details for first 5
                    print(f"✅ Fixed: {episode['episode_title'][:40]}...")
                    print(f"   Moved to: {episode['correct_feed_title']}")

        conn.commit()

    print(f"\n✅ Successfully fixed {fixed_count} episodes")

    # Update feed last_episode_date for all affected feeds
    print("\nUpdating feed last_episode_date values...")
    with engine.connect() as conn:
        for feed_id in affected_feeds:
            latest_result = conn.execute(text("""
                SELECT MAX(published_date) as latest_date
                FROM episodes
                WHERE feed_id = :feed_id
            """), {'feed_id': feed_id})

            latest_date = latest_result.scalar()

            if latest_date:
                conn.execute(text("""
                    UPDATE feeds
                    SET last_episode_date = :latest_date, updated_at = NOW()
                    WHERE id = :feed_id
                """), {'latest_date': latest_date, 'feed_id': feed_id})
            else:
                conn.execute(text("""
                    UPDATE feeds
                    SET last_episode_date = NULL, updated_at = NOW()
                    WHERE id = :feed_id
                """), {'feed_id': feed_id})

        conn.commit()

    print(f"✅ Updated last_episode_date for {len(affected_feeds)} feeds")


if __name__ == "__main__":
    misassigned = analyze_migration_issues()
    if misassigned:
        print(f"\nProceeding to fix {len(misassigned)} episodes...")
        fix_all_assignments(misassigned)
    else:
        print("No fixes needed!")