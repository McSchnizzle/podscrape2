#!/usr/bin/env python3
"""
Investigate digest-episode associations to find incorrect "Included In" data.
Check for episodes that should be linked to digests but aren't, and vice versa.
"""

import sys
import sqlite3
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from config.env import require_database_url
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import json


def investigate_digest_episodes():
    """Investigate digest-episode associations."""

    load_dotenv()
    db_url = require_database_url()
    pg_engine = create_engine(db_url)

    print('Investigating digest-episode associations...\n')

    # Step 1: Check current digest data
    print("Step 1: Current Supabase digest data")
    print("-" * 60)

    with pg_engine.connect() as conn:
        digests_result = conn.execute(text('''
            SELECT id, topic, digest_date, episode_ids, episode_count
            FROM digests
            ORDER BY digest_date DESC
        '''))

        digests = []
        for row in digests_result:
            digest_info = {
                'id': row.id,
                'topic': row.topic,
                'date': str(row.digest_date),
                'episode_ids': row.episode_ids or [],
                'episode_count': row.episode_count or 0
            }
            digests.append(digest_info)

            print(f"Digest: {row.topic} ({row.digest_date})")
            print(f"  Episode IDs: {row.episode_ids}")
            print(f"  Episode Count: {row.episode_count}")
            print()

    # Step 2: Check if episode IDs in digests actually exist
    print("Step 2: Validating episode IDs in digests")
    print("-" * 60)

    missing_episodes = []
    valid_episodes = []

    with pg_engine.connect() as conn:
        for digest in digests:
            if digest['episode_ids']:
                for episode_id in digest['episode_ids']:
                    result = conn.execute(text('''
                        SELECT id, title, episode_guid
                        FROM episodes
                        WHERE id = :episode_id
                    '''), {'episode_id': episode_id})

                    episode = result.fetchone()
                    if episode:
                        valid_episodes.append({
                            'digest_topic': digest['topic'],
                            'digest_date': digest['date'],
                            'episode_id': episode_id,
                            'episode_title': episode.title
                        })
                    else:
                        missing_episodes.append({
                            'digest_topic': digest['topic'],
                            'digest_date': digest['date'],
                            'missing_episode_id': episode_id
                        })

    print(f"Valid episode associations: {len(valid_episodes)}")
    print(f"Missing episode references: {len(missing_episodes)}")

    if missing_episodes:
        print("\nMissing episode IDs in digests:")
        for missing in missing_episodes:
            print(f"  Digest '{missing['digest_topic']}' ({missing['digest_date']}) → Episode ID {missing['missing_episode_id']} NOT FOUND")

    # Step 3: Compare with SQLite to see what the original associations were
    print(f"\nStep 3: Comparing with original SQLite data")
    print("-" * 60)

    sqlite_path = Path(__file__).parent.parent / "data" / "database" / "_digest.db"
    sqlite_conn = sqlite3.connect(str(sqlite_path))
    sqlite_conn.row_factory = sqlite3.Row

    print("Original SQLite digest data:")
    sqlite_cursor = sqlite_conn.execute('''
        SELECT id, topic, digest_date, episode_ids, episode_count
        FROM digests
        ORDER BY digest_date DESC
    ''')

    sqlite_digests = []
    for row in sqlite_cursor:
        episode_ids = json.loads(row['episode_ids']) if row['episode_ids'] else []
        sqlite_digests.append({
            'id': row['id'],
            'topic': row['topic'],
            'date': str(row['digest_date']),
            'episode_ids': episode_ids,
            'episode_count': row['episode_count'] or 0
        })

        print(f"SQLite Digest: {row['topic']} ({row['digest_date']})")
        print(f"  Episode IDs: {episode_ids}")
        print(f"  Episode Count: {row['episode_count']}")
        print()

    # Step 4: Check if the episode GUIDs can help us map correctly
    print("Step 4: Checking episode GUID mapping between SQLite and Supabase")
    print("-" * 60)

    # Build mapping of episode_id to GUID from SQLite
    sqlite_id_to_guid = {}
    sqlite_cursor = sqlite_conn.execute('SELECT id, episode_guid FROM episodes')
    for row in sqlite_cursor:
        sqlite_id_to_guid[row['id']] = row['episode_guid']

    # Build mapping of GUID to episode_id from Supabase
    supabase_guid_to_id = {}
    with pg_engine.connect() as conn:
        result = conn.execute(text('SELECT id, episode_guid FROM episodes'))
        for row in result:
            supabase_guid_to_id[row.episode_guid] = row.id

    # Now check if we can fix the digest associations
    print("Attempting to map SQLite episode IDs to current Supabase IDs:")

    fixes_needed = []
    for sqlite_digest in sqlite_digests:
        if sqlite_digest['episode_ids']:
            current_episode_ids = []
            for sqlite_episode_id in sqlite_digest['episode_ids']:
                if sqlite_episode_id in sqlite_id_to_guid:
                    episode_guid = sqlite_id_to_guid[sqlite_episode_id]
                    if episode_guid in supabase_guid_to_id:
                        current_episode_id = supabase_guid_to_id[episode_guid]
                        current_episode_ids.append(current_episode_id)
                        print(f"  ✅ SQLite ID {sqlite_episode_id} → GUID {episode_guid} → Supabase ID {current_episode_id}")
                    else:
                        print(f"  ❌ GUID {episode_guid} not found in Supabase")
                else:
                    print(f"  ❌ SQLite episode ID {sqlite_episode_id} not found")

            # Check if this digest needs updating
            supabase_digest = next((d for d in digests if d['topic'] == sqlite_digest['topic'] and d['date'] == sqlite_digest['date']), None)
            if supabase_digest:
                if set(current_episode_ids) != set(supabase_digest['episode_ids']):
                    fixes_needed.append({
                        'digest_id': supabase_digest['id'],
                        'topic': sqlite_digest['topic'],
                        'date': sqlite_digest['date'],
                        'current_episode_ids': supabase_digest['episode_ids'],
                        'correct_episode_ids': current_episode_ids
                    })

    sqlite_conn.close()

    print(f"\nStep 5: Summary")
    print("-" * 60)
    print(f"Digests needing episode ID fixes: {len(fixes_needed)}")

    if fixes_needed:
        print("\nDigests that need fixing:")
        for fix in fixes_needed:
            print(f"  {fix['topic']} ({fix['date']})")
            print(f"    Current: {fix['current_episode_ids']}")
            print(f"    Should be: {fix['correct_episode_ids']}")
            print()

    return fixes_needed


if __name__ == "__main__":
    investigate_digest_episodes()