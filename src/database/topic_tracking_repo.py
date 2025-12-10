"""
TopicTrackingRepository: Data access for episode_topics table.
Manages topic extraction, deduplication, and history tracking.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from sqlalchemy import text

from src.database.sqlalchemy_models import EpisodeTopic
from src.database.models import get_database_manager


class TopicTrackingRepository:
    """Repository for episode_topics table operations"""

    def __init__(self):
        self.db_manager = get_database_manager()

    def store_topic(
        self,
        episode_id: int,
        topic_name: str,
        key_points: List[str],
        digest_topic: str,
        relevance_score: float,
    ) -> EpisodeTopic:
        """
        Store or update topic for episode.
        Uses UPSERT pattern to handle re-scoring scenarios.

        Args:
            episode_id: Episode database ID
            topic_name: Human-readable topic name
            key_points: List of key insights (2-4 items)
            digest_topic: Parent topic (e.g., "AI and Technology")
            relevance_score: Episode's relevance score for digest_topic

        Returns:
            EpisodeTopic: The created or updated topic record
        """
        topic_slug = self._normalize_topic_name(topic_name)
        now = datetime.now(timezone.utc)

        with self.db_manager.get_session() as session:
            # Check if topic already exists (by slug)
            existing = (
                session.query(EpisodeTopic)
                .filter(
                    EpisodeTopic.episode_id == episode_id,
                    EpisodeTopic.topic_slug == topic_slug,
                )
                .first()
            )

            if existing:
                # Update existing record
                existing.topic_name = topic_name  # Update in case of minor name changes
                existing.key_points = key_points
                existing.last_mentioned_at = now
                existing.updated_at = now
                existing.mention_count += 1
                session.commit()
                return existing
            else:
                # Create new record
                new_topic = EpisodeTopic(
                    episode_id=episode_id,
                    topic_name=topic_name,
                    topic_slug=topic_slug,
                    key_points=key_points,
                    digest_topic=digest_topic,
                    relevance_score=relevance_score,
                    first_mentioned_at=now,
                    last_mentioned_at=now,
                    mention_count=1,
                )
                session.add(new_topic)
                session.commit()
                session.refresh(new_topic)
                return new_topic

    def get_recent_topics_for_digest(
        self, digest_topic: str, days_back: int = 14
    ) -> List[Dict]:
        """
        Get recent topics covered for a digest topic.
        Used to provide context during digest generation.

        Args:
            digest_topic: Parent topic name (e.g., "AI and Technology")
            days_back: How many days of history to retrieve

        Returns:
            List of topic dictionaries with all fields
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

        with self.db_manager.get_session() as session:
            topics = (
                session.query(EpisodeTopic)
                .filter(
                    EpisodeTopic.digest_topic == digest_topic,
                    EpisodeTopic.last_mentioned_at >= cutoff_date,
                )
                .order_by(EpisodeTopic.last_mentioned_at.desc())
                .all()
            )

            return [self._to_dict(t) for t in topics]

    def get_topics_for_episode(self, episode_id: int) -> List[Dict]:
        """
        Get all topics extracted from a specific episode.

        Args:
            episode_id: Episode database ID

        Returns:
            List of topic dictionaries
        """
        with self.db_manager.get_session() as session:
            topics = (
                session.query(EpisodeTopic)
                .filter(EpisodeTopic.episode_id == episode_id)
                .all()
            )

            return [self._to_dict(t) for t in topics]

    def mark_topics_as_included(
        self, episode_ids: List[int], digest_id: int
    ) -> int:
        """
        Mark topics from episodes as included in digest.
        Prevents re-using same topics immediately.

        Args:
            episode_ids: List of episode IDs included in digest
            digest_id: Digest database ID

        Returns:
            Number of topics marked
        """
        now = datetime.now(timezone.utc)

        with self.db_manager.get_session() as session:
            result = (
                session.query(EpisodeTopic)
                .filter(
                    EpisodeTopic.episode_id.in_(episode_ids),
                    EpisodeTopic.included_in_digest_id == None,  # noqa: E711
                )
                .update(
                    {
                        "included_in_digest_id": digest_id,
                        "included_at": now,
                        "updated_at": now,
                    },
                    synchronize_session=False,
                )
            )
            session.commit()
            return result

    def delete_old_topics(self, days_old: int) -> int:
        """
        Delete topics older than specified days.
        Part of retention management.

        Args:
            days_old: Delete topics last mentioned more than this many days ago

        Returns:
            Number of topics deleted
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)

        with self.db_manager.get_session() as session:
            result = (
                session.query(EpisodeTopic)
                .filter(EpisodeTopic.last_mentioned_at < cutoff_date)
                .delete(synchronize_session=False)
            )
            session.commit()
            return result

    def get_topic_stats(self, digest_topic: str, days_back: int = 14) -> Dict:
        """
        Get statistics about topics for a digest topic.
        Useful for debugging and monitoring.

        Args:
            digest_topic: Parent topic name
            days_back: Time window for statistics

        Returns:
            Dictionary with statistics
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

        with self.db_manager.get_session() as session:
            # Total topics
            total_topics = (
                session.query(EpisodeTopic)
                .filter(
                    EpisodeTopic.digest_topic == digest_topic,
                    EpisodeTopic.last_mentioned_at >= cutoff_date,
                )
                .count()
            )

            # Topics included in digests
            included_topics = (
                session.query(EpisodeTopic)
                .filter(
                    EpisodeTopic.digest_topic == digest_topic,
                    EpisodeTopic.last_mentioned_at >= cutoff_date,
                    EpisodeTopic.included_in_digest_id != None,  # noqa: E711
                )
                .count()
            )

            # Topics not yet included
            pending_topics = total_topics - included_topics

            # Most mentioned topics
            top_topics = (
                session.query(
                    EpisodeTopic.topic_slug,
                    EpisodeTopic.topic_name,
                    EpisodeTopic.mention_count,
                )
                .filter(
                    EpisodeTopic.digest_topic == digest_topic,
                    EpisodeTopic.last_mentioned_at >= cutoff_date,
                )
                .order_by(EpisodeTopic.mention_count.desc())
                .limit(10)
                .all()
            )

            return {
                "total_topics": total_topics,
                "included_topics": included_topics,
                "pending_topics": pending_topics,
                "top_topics": [
                    {
                        "slug": slug,
                        "name": name,
                        "mentions": count,
                    }
                    for slug, name, count in top_topics
                ],
            }

    def _normalize_topic_name(self, topic_name: str) -> str:
        """
        Normalize topic name to slug for deduplication.

        Examples:
            "GPT-5 Release" → "gpt-5-release"
            "OpenAI Crisis!" → "openai-crisis"
            "Meta's AI Push" → "metas-ai-push"

        Args:
            topic_name: Original topic name

        Returns:
            Normalized slug
        """
        # Lowercase
        slug = topic_name.lower()
        # Remove special characters except spaces and hyphens
        slug = re.sub(r"[^\w\s-]", "", slug)
        # Replace multiple spaces/hyphens with single hyphen
        slug = re.sub(r"[-\s]+", "-", slug)
        # Strip leading/trailing hyphens
        slug = slug.strip("-")
        return slug

    def _to_dict(self, topic: EpisodeTopic) -> Dict:
        """Convert EpisodeTopic model to dictionary"""
        return {
            "id": topic.id,
            "episode_id": topic.episode_id,
            "topic_name": topic.topic_name,
            "topic_slug": topic.topic_slug,
            "key_points": topic.key_points,
            "first_mentioned_at": topic.first_mentioned_at,
            "last_mentioned_at": topic.last_mentioned_at,
            "mention_count": topic.mention_count,
            "digest_topic": topic.digest_topic,
            "relevance_score": topic.relevance_score,
            "included_in_digest_id": topic.included_in_digest_id,
            "included_at": topic.included_at,
            "created_at": topic.created_at,
            "updated_at": topic.updated_at,
        }


# Factory function for consistency with existing repository pattern
def get_topic_tracking_repo() -> TopicTrackingRepository:
    """Get TopicTrackingRepository instance"""
    return TopicTrackingRepository()
