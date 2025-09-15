#!/usr/bin/env python3
"""
Check and verify feed-episode associations in the database.
Identifies mismatches between stored last_episode_date and actual latest episodes.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from config.env import require_database_url
from sqlalchemy import create_engine, text
from dotenv import load_dotenv


def check_feed_associations():
    """Check feed-episode associations for mismatches."""

    load_dotenv()
    db_url = require_database_url()
    engine = create_engine(db_url)

    print('Checking feed-episode associations...\n')

    with engine.connect() as conn:
        result = conn.execute(text('''
            SELECT f.id, f.title, f.feed_url, f.last_episode_date,
                   COUNT(e.id) as episode_count,
                   MAX(e.published_date) as actual_latest_episode
            FROM feeds f
            LEFT JOIN episodes e ON f.id = e.feed_id
            GROUP BY f.id, f.title, f.feed_url, f.last_episode_date
            ORDER BY f.id
        '''))

        print('Feed ID | Title | Episode Count | Stored Latest | Actual Latest | Match?')
        print('-' * 100)

        mismatches = []
        for row in result:
            stored = str(row.last_episode_date)[:10] if row.last_episode_date else 'None'
            actual = str(row.actual_latest_episode)[:10] if row.actual_latest_episode else 'None'

            # Check for mismatch
            is_mismatch = False
            if row.last_episode_date and row.actual_latest_episode:
                stored_date = str(row.last_episode_date)[:10]
                actual_date = str(row.actual_latest_episode)[:10]
                is_mismatch = stored_date != actual_date
            elif row.last_episode_date and not row.actual_latest_episode:
                is_mismatch = True
            elif not row.last_episode_date and row.actual_latest_episode:
                is_mismatch = True

            match = '❌' if is_mismatch else '✅'
            if is_mismatch:
                mismatches.append((row.id, row.title, stored, actual, row.episode_count))

            title_short = row.title[:35] + '...' if len(row.title) > 35 else row.title
            print(f'{row.id:7} | {title_short:38} | {row.episode_count:13} | {stored:13} | {actual:13} | {match}')

        print(f'\nTotal mismatches found: {len(mismatches)}')
        if mismatches:
            print('\nMismatched feeds:')
            for feed_id, title, stored, actual, count in mismatches:
                print(f'  Feed {feed_id}: {title[:50]}')
                print(f'    Stored: {stored}, Actual: {actual}, Episodes: {count}')

        return mismatches


if __name__ == "__main__":
    check_feed_associations()