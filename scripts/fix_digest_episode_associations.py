#!/usr/bin/env python3
"""
Fix digest-episode associations by updating episode_ids to use current Supabase IDs.
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


def fix_digest_episode_associations():
    """Fix digest-episode associations using GUID mapping."""

    load_dotenv()
    db_url = require_database_url()
    pg_engine = create_engine(db_url)

    print('Fixing digest-episode associations...\n')

    # Step 1: Build GUID mapping from SQLite to Supabase
    print("Step 1: Building episode ID mapping...")
    print("-" * 50)

    sqlite_path = Path(__file__).parent.parent / "data" / "database" / "_digest.db"
    sqlite_conn = sqlite3.connect(str(sqlite_path))
    sqlite_conn.row_factory = sqlite3.Row

    # Get SQLite episode ID → GUID mapping
    sqlite_id_to_guid = {}
    sqlite_cursor = sqlite_conn.execute('SELECT id, episode_guid FROM episodes')
    for row in sqlite_cursor:
        sqlite_id_to_guid[row['id']] = row['episode_guid']

    # Get Supabase GUID → episode ID mapping
    supabase_guid_to_id = {}
    with pg_engine.connect() as conn:
        result = conn.execute(text('SELECT id, episode_guid FROM episodes'))
        for row in result:
            supabase_guid_to_id[row.episode_guid] = row.id

    print(f"Found {len(sqlite_id_to_guid)} SQLite episodes")
    print(f"Found {len(supabase_guid_to_id)} Supabase episodes")

    # Step 2: Get SQLite digest data and map to current episode IDs
    print("\nStep 2: Processing digest episode associations...")
    print("-" * 50)

    fixes_to_apply = []

    sqlite_cursor = sqlite_conn.execute('''
        SELECT id, topic, digest_date, episode_ids, episode_count
        FROM digests
        ORDER BY digest_date DESC
    ''')

    for row in sqlite_cursor:
        sqlite_episode_ids = json.loads(row['episode_ids']) if row['episode_ids'] else []

        if not sqlite_episode_ids:
            continue

        # Map SQLite episode IDs to current Supabase IDs
        current_episode_ids = []
        unmapped_ids = []

        for sqlite_id in sqlite_episode_ids:
            if sqlite_id in sqlite_id_to_guid:
                guid = sqlite_id_to_guid[sqlite_id]
                if guid in supabase_guid_to_id:
                    current_id = supabase_guid_to_id[guid]
                    current_episode_ids.append(current_id)
                else:
                    unmapped_ids.append(f"GUID {guid} not in Supabase")
            else:
                unmapped_ids.append(f"SQLite ID {sqlite_id} not found")

        # Find corresponding Supabase digest
        with pg_engine.connect() as conn:
            supabase_digest = conn.execute(text('''
                SELECT id, episode_ids
                FROM digests
                WHERE topic = :topic AND digest_date = :date
            '''), {
                'topic': row['topic'],
                'date': row['digest_date']
            }).fetchone()

            if supabase_digest:
                current_supabase_ids = supabase_digest.episode_ids or []

                if set(current_episode_ids) != set(current_supabase_ids):
                    fixes_to_apply.append({
                        'digest_id': supabase_digest.id,
                        'topic': row['topic'],
                        'date': str(row['digest_date']),
                        'old_episode_ids': current_supabase_ids,
                        'new_episode_ids': current_episode_ids,
                        'unmapped': unmapped_ids
                    })

                    print(f"Digest: {row['topic']} ({row['digest_date']})")
                    print(f"  Old IDs: {current_supabase_ids}")
                    print(f"  New IDs: {current_episode_ids}")
                    if unmapped_ids:
                        print(f"  Unmapped: {unmapped_ids}")
                    print()

    sqlite_conn.close()

    if not fixes_to_apply:
        print("✅ No digest episode associations need fixing!")
        return

    print(f"Step 3: Applying {len(fixes_to_apply)} fixes...")
    print("-" * 50)

    fixed_count = 0
    with pg_engine.connect() as conn:
        for fix in fixes_to_apply:
            try:
                result = conn.execute(text('''
                    UPDATE digests
                    SET episode_ids = CAST(:new_episode_ids AS jsonb),
                        episode_count = :episode_count
                    WHERE id = :digest_id
                '''), {
                    'new_episode_ids': json.dumps(fix['new_episode_ids']),
                    'episode_count': len(fix['new_episode_ids']),
                    'digest_id': fix['digest_id']
                })

                if result.rowcount > 0:
                    fixed_count += 1
                    print(f"✅ Fixed: {fix['topic']} ({fix['date']})")
                    print(f"   Episodes: {len(fix['old_episode_ids'])} → {len(fix['new_episode_ids'])}")
                else:
                    print(f"❌ Failed to update: {fix['topic']} ({fix['date']})")

            except Exception as e:
                print(f"❌ Error updating {fix['topic']}: {e}")

        conn.commit()

    print(f"\n✅ Successfully fixed {fixed_count} out of {len(fixes_to_apply)} digests")

    # Step 4: Verification
    print("\nStep 4: Verification...")
    print("-" * 50)

    with pg_engine.connect() as conn:
        # Check for any remaining missing episode references
        missing_check = conn.execute(text('''
            WITH digest_episodes AS (
                SELECT d.id as digest_id, d.topic, d.digest_date,
                       jsonb_array_elements_text(d.episode_ids::jsonb)::int as episode_id
                FROM digests d
                WHERE d.episode_ids IS NOT NULL
            )
            SELECT de.topic, de.digest_date, de.episode_id
            FROM digest_episodes de
            WHERE NOT EXISTS (
                SELECT 1 FROM episodes e WHERE e.id = de.episode_id
            )
        ''')).fetchall()

        if missing_check:
            print(f"⚠️  Still have {len(missing_check)} missing episode references:")
            for missing in missing_check:
                print(f"  {missing.topic} ({missing.digest_date}) → Episode ID {missing.episode_id}")
        else:
            print("✅ All digest episode references are now valid!")


if __name__ == "__main__":
    fix_digest_episode_associations()