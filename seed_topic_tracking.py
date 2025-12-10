#!/usr/bin/env python3
"""
Seed Topic Tracking Database

Seeds the episode_topics table with topics extracted from existing episodes.
Uses the same TopicExtractor code as the normal audio pipeline.

Usage:
    python3 seed_topic_tracking.py --topic "AI and Technology" --days 14
    python3 seed_topic_tracking.py --all-topics --days 30
"""

import argparse
import logging
from datetime import datetime, timedelta, timezone
from typing import List

from src.database.models import get_episode_repo, get_topic_repo
from src.topic_tracking.topic_extractor import TopicExtractor
from src.config.web_config import WebConfigManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def seed_topics_for_digest(digest_topic_name: str, days_back: int):
    """
    Seed topics for a specific digest topic from existing episodes.

    Args:
        digest_topic_name: Name of digest topic (e.g., "AI and Technology")
        days_back: Number of days to look back for episodes
    """
    logger.info(f"🌱 Seeding topics for '{digest_topic_name}' from last {days_back} days...")

    # Get repositories
    episode_repo = get_episode_repo()
    topic_repo = get_topic_repo()
    web_config = WebConfigManager()

    # Get the digest topic from database
    topic = topic_repo.get_topic_by_name(digest_topic_name)
    if not topic:
        logger.error(f"Digest topic '{digest_topic_name}' not found in database")
        return

    if not topic.is_active:
        logger.warning(f"Digest topic '{digest_topic_name}' is not active")
        return

    # Check if topic tracking is enabled
    if not topic.enable_topic_tracking:
        logger.warning(
            f"Topic tracking not enabled for '{digest_topic_name}'. "
            f"Enable it in the Web UI Topics page first."
        )
        return

    # Get score threshold
    min_score = web_config.get_setting("topic_tracking", "min_score_for_extraction", 0.70)

    # Calculate cutoff date
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

    # Get episodes from last N days with scores >= threshold
    logger.info(f"Fetching episodes from last {days_back} days with score >= {min_score}...")

    all_episodes = episode_repo.get_recent_episodes(days_back)

    # Filter episodes with transcripts and high scores for this topic
    qualifying_episodes = []
    for episode in all_episodes:
        # Check if episode has transcript
        if not episode.transcript or episode.transcript.strip() == "":
            continue

        # Check score for this topic
        if episode.scores and episode.scores.get(digest_topic_name, 0.0) >= min_score:
            qualifying_episodes.append(episode)

    logger.info(f"Found {len(qualifying_episodes)} episodes qualifying for topic extraction")

    if not qualifying_episodes:
        logger.info("No qualifying episodes found. Seeding complete.")
        return

    # Initialize TopicExtractor
    try:
        extractor = TopicExtractor()
    except Exception as e:
        logger.error(f"Failed to initialize TopicExtractor: {e}")
        return

    # Process each episode
    success_count = 0
    error_count = 0

    for i, episode in enumerate(qualifying_episodes, 1):
        try:
            logger.info(
                f"[{i}/{len(qualifying_episodes)}] Processing: {episode.title} "
                f"(score: {episode.scores.get(digest_topic_name, 0.0):.2f})"
            )

            # Extract and store topics
            topics = extractor.extract_and_store_topics(
                episode_guid=episode.episode_guid,
                digest_topic=digest_topic_name,
                transcript=episode.transcript,
                relevance_score=episode.scores.get(digest_topic_name, 0.0)
            )

            if topics:
                logger.info(f"✓ Extracted {len(topics)} topics from episode")
                for topic in topics:
                    logger.info(
                        f"  - {topic['name']} ({topic.get('type', 'other')}) "
                        f"[novelty: {topic.get('novelty_score', 1.0):.2f}]"
                    )
                success_count += 1
            else:
                logger.warning(f"No topics extracted from episode")

        except Exception as e:
            logger.error(f"✗ Failed to process episode {episode.episode_guid}: {e}")
            error_count += 1
            continue

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"Seeding complete for '{digest_topic_name}'")
    logger.info(f"Successfully processed: {success_count}/{len(qualifying_episodes)} episodes")
    if error_count > 0:
        logger.warning(f"Errors: {error_count}")
    logger.info(f"{'='*60}\n")


def seed_all_topics(days_back: int):
    """
    Seed topics for all active digest topics with topic_tracking enabled.

    Args:
        days_back: Number of days to look back for episodes
    """
    logger.info(f"🌱 Seeding topics for ALL active topics from last {days_back} days...")

    topic_repo = get_topic_repo()

    # Get all active topics with tracking enabled
    all_topics = topic_repo.get_all_topics()
    tracking_enabled_topics = [
        t for t in all_topics
        if t.is_active and t.enable_topic_tracking
    ]

    if not tracking_enabled_topics:
        logger.warning("No topics found with topic tracking enabled")
        logger.info("Enable topic tracking in the Web UI Topics page first")
        return

    logger.info(f"Found {len(tracking_enabled_topics)} topics with tracking enabled:")
    for topic in tracking_enabled_topics:
        logger.info(f"  - {topic.name}")

    # Seed each topic
    for topic in tracking_enabled_topics:
        seed_topics_for_digest(topic.name, days_back)
        logger.info("")  # Add spacing between topics


def main():
    parser = argparse.ArgumentParser(
        description="Seed topic tracking database from existing episode transcripts"
    )
    parser.add_argument(
        "--topic",
        type=str,
        help="Specific digest topic name to seed (e.g., 'AI and Technology')"
    )
    parser.add_argument(
        "--all-topics",
        action="store_true",
        help="Seed all topics with topic tracking enabled"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=14,
        help="Number of days to look back (default: 14)"
    )

    args = parser.parse_args()

    if not args.topic and not args.all_topics:
        parser.error("Must specify either --topic or --all-topics")

    logger.info("=" * 60)
    logger.info("Topic Tracking Database Seeder")
    logger.info("=" * 60)
    logger.info("")

    if args.all_topics:
        seed_all_topics(args.days)
    else:
        seed_topics_for_digest(args.topic, args.days)

    logger.info("✓ Seeding complete! Check the database for results:")
    logger.info("  SELECT COUNT(*) FROM episode_topics;")
    logger.info("  SELECT topic_type, COUNT(*) FROM episode_topics GROUP BY topic_type;")


if __name__ == "__main__":
    main()
