#!/usr/bin/env python3
"""
Investigate episodes that appear to have incorrect feed assignments.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from config.env import require_database_url
from sqlalchemy import create_engine, text
from dotenv import load_dotenv


def investigate_episode_feeds():
    """Investigate episodes with potentially incorrect feed assignments."""

    load_dotenv()
    db_url = require_database_url()
    engine = create_engine(db_url)

    print('Investigating episode-feed assignments...\n')

    # Check the specific problematic episodes
    problematic_titles = [
        "THE CHAMPAGNE ROOM: IT'S NOT A GLIZZY, IT'S A HEBREW NATIONAL!",
        "EP. 788: NO TRUE LEFTIST ft. BEN BURGIS",
        "Camille Sojit Pejcha: Sex vs. Capitalism",
        "BEYOND THE RED ZONE: 2025 NFL PREVIEW",
        "THE CHAMPAGNE ROOM: FROM THE MUFFIN TROUGH TO THE MEAT PARADE"
    ]

    with engine.connect() as conn:
        print("Checking specific problematic episodes:")
        print("-" * 100)

        for title in problematic_titles:
            result = conn.execute(text('''
                SELECT e.id, e.title, e.feed_id, e.audio_url, e.episode_guid,
                       f.title as feed_title, f.feed_url
                FROM episodes e
                JOIN feeds f ON e.feed_id = f.id
                WHERE e.title LIKE :title
            '''), {'title': f'%{title[:30]}%'})

            row = result.fetchone()
            if row:
                print(f"Episode: {row.title[:60]}...")
                print(f"  Assigned Feed: {row.feed_title}")
                print(f"  Feed URL: {row.feed_url}")
                print(f"  Audio URL: {row.audio_url[:80]}...")
                print(f"  Episode GUID: {row.episode_guid}")
                print()

        print("\n" + "="*100)
        print("FEED ANALYSIS - Looking for patterns")
        print("="*100)

        # Get all feeds and their typical audio URL patterns
        feeds_result = conn.execute(text('''
            SELECT f.id, f.title, f.feed_url,
                   COUNT(e.id) as episode_count,
                   STRING_AGG(DISTINCT SUBSTRING(e.audio_url FROM 'https://([^/]+)'), ', ') as audio_domains
            FROM feeds f
            LEFT JOIN episodes e ON f.id = e.feed_id
            WHERE f.id IN (SELECT DISTINCT feed_id FROM episodes WHERE feed_id IS NOT NULL)
            GROUP BY f.id, f.title, f.feed_url
            ORDER BY f.id
        '''))

        print("\nFeed ID | Feed Title | Episodes | Audio Domains")
        print("-" * 80)

        for row in feeds_result:
            print(f"{row.id:7} | {row.title[:30]:30} | {row.episode_count:8} | {row.audio_domains or 'None'}")

        print("\n" + "="*100)
        print("DETAILED EPISODE ANALYSIS")
        print("="*100)

        # Check episodes with their audio URLs to identify patterns
        episodes_result = conn.execute(text('''
            SELECT e.id, e.title, e.feed_id, e.audio_url, e.episode_guid,
                   f.title as feed_title, f.feed_url
            FROM episodes e
            JOIN feeds f ON e.feed_id = f.id
            WHERE e.title IN (
                'THE CHAMPAGNE ROOM: IT''S NOT A GLIZZY, IT''S A HEBREW NATIONAL!',
                'EP. 788: NO TRUE LEFTIST ft. BEN BURGIS',
                'Camille Sojit Pejcha: Sex vs. Capitalism',
                'BEYOND THE RED ZONE: 2025 NFL PREVIEW',
                'THE CHAMPAGNE ROOM: FROM THE MUFFIN TROUGH TO THE MEAT PARADE'
            ) OR e.title LIKE '%CHAMPAGNE ROOM%' OR e.title LIKE '%EP. 788%'
            ORDER BY e.title
        '''))

        for row in episodes_result:
            print(f"\nEpisode: {row.title}")
            print(f"  Current Feed: {row.feed_title}")
            print(f"  Feed URL: {row.feed_url}")
            print(f"  Audio URL: {row.audio_url}")

            # Try to determine correct feed from audio URL
            if 'anchor.fm' in row.audio_url:
                print(f"  → Audio suggests: Anchor-hosted podcast")
            elif 'simplecast' in row.audio_url:
                print(f"  → Audio suggests: Simplecast-hosted podcast")
            elif 'libsyn' in row.audio_url:
                print(f"  → Audio suggests: Libsyn-hosted podcast")
            elif 'megaphone' in row.audio_url:
                print(f"  → Audio suggests: Megaphone-hosted podcast")


if __name__ == "__main__":
    investigate_episode_feeds()