#!/usr/bin/env python3
"""
Update Episode Relevance Status
Updates existing episodes marked as 'scored' to 'not_relevant' if they don't qualify for any topic.
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
    print("🔍 Updating episode relevance status...")

    # Initialize components
    episode_repo = get_episode_repo()

    # Get threshold from web config
    try:
        web_config = WebConfigManager()
        threshold = float(web_config.get_setting('content_filtering', 'score_threshold', 0.65))
    except Exception:
        threshold = 0.65

    print(f"📊 Using relevance threshold: {threshold}")

    # Get all scored episodes
    print("🔍 Finding episodes with 'scored' status...")

    # Get episodes that are currently marked as 'scored'
    scored_episodes = episode_repo.get_by_status('scored')
    print(f"Found {len(scored_episodes)} episodes with 'scored' status")

    if not scored_episodes:
        print("✅ No scored episodes found - nothing to update")
        return

    episodes_to_update = []
    episodes_still_relevant = []

    for episode in scored_episodes:
        if not episode.scores:
            print(f"⚠️  Episode {episode.episode_guid} has no scores - keeping as 'scored'")
            continue

        # Check if episode qualifies for any topic
        qualifying_topics = []
        for topic, score in episode.scores.items():
            if score >= threshold:
                qualifying_topics.append(topic)

        if qualifying_topics:
            episodes_still_relevant.append(episode)
            print(f"✅ {episode.title[:50]}... - Qualifies for {len(qualifying_topics)} topics")
        else:
            episodes_to_update.append(episode)
            max_score = max(episode.scores.values()) if episode.scores else 0
            print(f"❌ {episode.title[:50]}... - No qualifying topics (max: {max_score:.2f})")

    print(f"\n📊 Summary:")
    print(f"   Still relevant: {len(episodes_still_relevant)} episodes")
    print(f"   Not relevant: {len(episodes_to_update)} episodes")

    if not episodes_to_update:
        print("✅ All scored episodes are still relevant - no updates needed")
        return

    # Auto-confirm update for non-interactive environment
    print(f"\n✅ Proceeding to update {len(episodes_to_update)} episodes to 'not_relevant' status...")

    # Update episodes
    print(f"\n🔄 Updating {len(episodes_to_update)} episodes...")
    updated_count = 0

    for episode in episodes_to_update:
        try:
            episode_repo.update_status(episode.episode_guid, 'not_relevant')
            updated_count += 1
            print(f"   ✓ Updated: {episode.title[:50]}...")
        except Exception as e:
            print(f"   ❌ Failed to update {episode.episode_guid}: {e}")

    print(f"\n✅ Successfully updated {updated_count}/{len(episodes_to_update)} episodes to 'not_relevant' status")

    # Show final statistics
    print(f"\n📈 Final episode status distribution:")
    for status in ['pending', 'transcribed', 'scored', 'digested', 'not_relevant', 'failed']:
        count = len(episode_repo.get_by_status(status))
        print(f"   {status}: {count} episodes")

if __name__ == '__main__':
    main()