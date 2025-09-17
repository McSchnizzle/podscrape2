#!/usr/bin/env python3
"""
Score Remaining Transcribed Episodes
Scores all episodes with 'transcribed' status.
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
from src.scoring.content_scorer import ContentScorer
from src.config.web_config import WebConfigManager

def main():
    print("🔍 Scoring remaining transcribed episodes...")

    # Initialize components
    episode_repo = get_episode_repo()
    content_scorer = ContentScorer()

    # Get threshold from web config
    try:
        web_config = WebConfigManager()
        threshold = float(web_config.get_setting('content_filtering', 'score_threshold', 0.65))
    except Exception:
        threshold = 0.65

    print(f"📊 Using relevance threshold: {threshold}")

    # Get episodes with 'transcribed' status
    transcribed_episodes = episode_repo.get_by_status('transcribed')
    print(f"Found {len(transcribed_episodes)} episodes with 'transcribed' status")

    if not transcribed_episodes:
        print("✅ No transcribed episodes found - nothing to score")
        return

    scored_count = 0
    for i, episode in enumerate(transcribed_episodes, 1):
        print(f"\n[{i}/{len(transcribed_episodes)}] Scoring: {episode.title}")

        if not episode.transcript_path or not Path(episode.transcript_path).exists():
            print(f"⚠️  No transcript found for episode {episode.episode_guid}")
            continue

        try:
            # Read transcript
            with open(episode.transcript_path, 'r', encoding='utf-8') as f:
                transcript = f.read()

            print(f"Transcript: {len(transcript):,} characters")

            # Score the episode
            scoring_result = content_scorer.score_transcript(transcript, episode.episode_guid)

            if not scoring_result.success:
                print(f"❌ Scoring failed: {scoring_result.error_message}")
                continue

            # Update database with scores
            episode_repo.update_scores(episode.episode_guid, scoring_result.scores)

            # Determine status based on qualification
            qualifying_topics = []
            for topic, score in scoring_result.scores.items():
                if score >= threshold:
                    qualifying_topics.append(topic)

            if qualifying_topics:
                episode_status = 'scored'
                print(f"✅ Qualifies for {len(qualifying_topics)} topics: {', '.join(qualifying_topics)}")
            else:
                episode_status = 'not_relevant'
                max_score = max(scoring_result.scores.values()) if scoring_result.scores else 0
                print(f"❌ No qualifying topics (max: {max_score:.2f}) - marking as not relevant")

            # Update episode status
            episode_repo.update_status(episode.episode_guid, episode_status)

            print(f"📊 Topic Scores:")
            for topic, score in scoring_result.scores.items():
                status = "✅ QUALIFIES" if score >= threshold else "   "
                print(f"   {status} {topic:<35} {score:.2f}")

            scored_count += 1

        except Exception as e:
            print(f"❌ Failed to score episode: {e}")

    print(f"\n✅ Successfully scored {scored_count}/{len(transcribed_episodes)} episodes")

    # Show final statistics
    print(f"\n📈 Final episode status distribution:")
    for status in ['pending', 'transcribed', 'scored', 'digested', 'not_relevant', 'failed']:
        count = len(episode_repo.get_by_status(status))
        print(f"   {status}: {count} episodes")

if __name__ == '__main__':
    main()