#!/usr/bin/env python3
"""
Fix Episode Status Consistency
Updates episodes with 'transcribed' status that have actually been scored.
"""

import os
import sys
from pathlib import Path

# Add src to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

# Set up environment
from dotenv import load_dotenv
load_dotenv()
from src.config.env import require_database_url
require_database_url()

from src.database.models import get_episode_repo
from src.config.web_config import WebConfigManager

def main():
    print("🔍 Fixing episode status consistency...")

    # Initialize components
    episode_repo = get_episode_repo()

    # Get threshold from web config
    try:
        web_config = WebConfigManager()
        threshold = float(web_config.get_setting('content_filtering', 'score_threshold', 0.65))
    except Exception:
        threshold = 0.65

    print(f"📊 Using relevance threshold: {threshold}")

    # Get all transcribed episodes
    print("🔍 Finding episodes with 'transcribed' status...")
    transcribed_episodes = episode_repo.get_by_status('transcribed')
    print(f"Found {len(transcribed_episodes)} episodes with 'transcribed' status")

    if not transcribed_episodes:
        print("✅ No transcribed episodes found - nothing to fix")
        return

    episodes_to_score = []  # Episodes that need scoring (no scores)
    episodes_to_mark_scored = []  # Episodes with scores that qualify
    episodes_to_mark_not_relevant = []  # Episodes with scores that don't qualify

    for episode in transcribed_episodes:
        if not episode.scores:
            episodes_to_score.append(episode)
            print(f"⚠️  {episode.title[:50]}... - No scores, needs scoring")
        else:
            # Episode has scores but wrong status - determine correct status
            qualifying_topics = []
            for topic, score in episode.scores.items():
                if score >= threshold:
                    qualifying_topics.append(topic)

            if qualifying_topics:
                episodes_to_mark_scored.append(episode)
                print(f"✅ {episode.title[:50]}... - Has scores, qualifies for {len(qualifying_topics)} topics -> 'scored'")
            else:
                episodes_to_mark_not_relevant.append(episode)
                max_score = max(episode.scores.values()) if episode.scores else 0
                print(f"❌ {episode.title[:50]}... - Has scores, no qualifying topics (max: {max_score:.2f}) -> 'not_relevant'")

    print(f"\n📊 Summary:")
    print(f"   Need scoring: {len(episodes_to_score)} episodes")
    print(f"   Should be 'scored': {len(episodes_to_mark_scored)} episodes")
    print(f"   Should be 'not_relevant': {len(episodes_to_mark_not_relevant)} episodes")

    # Update episodes with scores to correct status
    total_updated = 0

    if episodes_to_mark_scored:
        print(f"\n🔄 Updating {len(episodes_to_mark_scored)} episodes to 'scored' status...")
        for episode in episodes_to_mark_scored:
            try:
                episode_repo.update_status(episode.episode_guid, 'scored')
                total_updated += 1
                print(f"   ✓ Updated to 'scored': {episode.title[:50]}...")
            except Exception as e:
                print(f"   ❌ Failed to update {episode.episode_guid}: {e}")

    if episodes_to_mark_not_relevant:
        print(f"\n🔄 Updating {len(episodes_to_mark_not_relevant)} episodes to 'not_relevant' status...")
        for episode in episodes_to_mark_not_relevant:
            try:
                episode_repo.update_status(episode.episode_guid, 'not_relevant')
                total_updated += 1
                print(f"   ✓ Updated to 'not_relevant': {episode.title[:50]}...")
            except Exception as e:
                print(f"   ❌ Failed to update {episode.episode_guid}: {e}")

    if episodes_to_score:
        print(f"\n⚠️  {len(episodes_to_score)} episodes still need scoring:")
        for episode in episodes_to_score[:5]:  # Show first 5
            print(f"   - {episode.title[:50]}...")
        if len(episodes_to_score) > 5:
            print(f"   ... and {len(episodes_to_score) - 5} more")
        print(f"\n💡 To score these episodes, run: python3 scripts/run_scoring.py")

    print(f"\n✅ Successfully updated {total_updated} episode statuses")

    # Show final statistics
    print(f"\n📈 Current episode status distribution:")
    for status in ['pending', 'transcribed', 'scored', 'digested', 'not_relevant', 'failed']:
        count = len(episode_repo.get_by_status(status))
        print(f"   {status}: {count} episodes")

if __name__ == '__main__':
    main()