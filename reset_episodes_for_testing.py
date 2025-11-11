#!/usr/bin/env python3
"""
Reset episodes for testing multi-voice dialogue functionality.
Finds 10 oldest episodes scored for Community Organizing and resets status to 'scored'.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from database.models import get_episode_repo

def reset_episodes_for_testing():
    """Reset 10 oldest Community Organizing episodes from 'digested' to 'scored'."""

    topic_name = "Social Movements and Community Organizing"
    score_threshold = 0.65

    repo = get_episode_repo()

    # Get all episodes that scored for Community Organizing (including digested ones)
    all_episodes = repo.get_scored_episodes_for_topic(
        topic=topic_name,
        min_score=score_threshold,
        exclude_digested=False  # Include digested episodes
    )

    # Filter for only digested episodes
    digested_episodes = [ep for ep in all_episodes if ep.status == 'digested']

    if not digested_episodes:
        print("No digested episodes found to reset.")
        return

    # Sort by published_date (oldest first) and take first 10
    digested_episodes.sort(key=lambda x: x.published_date if x.published_date else x.created_at)
    episodes_to_reset = digested_episodes[:10]

    print(f"Found {len(episodes_to_reset)} episodes to reset:\n")

    # Reset status to 'scored'
    for episode in episodes_to_reset:
        old_status = episode.status
        repo.update_status_by_id(episode.id, 'scored')

        pub_date = episode.published_date.strftime('%Y-%m-%d') if episode.published_date else 'Unknown'
        title = episode.title[:60] if episode.title else 'Unknown'
        score = episode.scores.get(topic_name, 0)

        print(f"  [{pub_date}] {title}")
        print(f"    Score: {score:.3f} | Status: {old_status} → scored")
        print()

    print(f"✅ Successfully reset {len(episodes_to_reset)} episodes to 'scored' status")
    print(f"   These episodes can now be included in new digest generation for testing.")

if __name__ == '__main__':
    reset_episodes_for_testing()
