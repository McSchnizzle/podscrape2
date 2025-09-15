#!/usr/bin/env python3
"""
Reset the status of the most recent episode to allow reprocessing
for testing the Turbo v2.5 model improvements.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Set up environment
from dotenv import load_dotenv
load_dotenv()

from database.models import get_episode_repo

def reset_latest_episode():
    """Reset the most recent episode status to 'pending' for reprocessing"""

    try:
        # Initialize episode repository
        episode_repo = get_episode_repo()

        # Get episodes that were processed (transcribed or scored)
        processed_episodes = episode_repo.get_by_status_list(['transcribed', 'scored'])

        if not processed_episodes:
            print("No processed episodes found to reset")
            return

        # Sort by published date to get the most recent
        recent_episode = max(processed_episodes, key=lambda ep: ep.published_date)

        print(f"Found recent episode:")
        print(f"  ID: {recent_episode.id}")
        print(f"  Title: {recent_episode.title[:60]}...")
        print(f"  Status: {recent_episode.status}")
        print(f"  Published: {recent_episode.published_date}")

        # Reset status to pending
        episode_repo.update_status(recent_episode.episode_guid, 'pending')

        print(f"\n✅ Reset episode {recent_episode.id} status to 'pending'")
        print("You can now run the pipeline to reprocess this episode with Turbo v2.5!")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    reset_latest_episode()