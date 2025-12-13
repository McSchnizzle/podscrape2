"""
NoveltyDetector: Determines if a topic contains new information.
Uses embedding similarity to compare key points.
"""

import logging
from typing import List, Dict, Tuple, Optional
from openai import OpenAI
import numpy as np
from datetime import datetime, timezone

from src.config.web_config import WebConfigManager

logger = logging.getLogger(__name__)


class NoveltyDetector:
    """
    Detects novelty in topics by comparing key points using embeddings.
    """

    def __init__(self, novelty_threshold: float = 0.30):
        """
        Initialize NoveltyDetector.

        Args:
            novelty_threshold: Minimum novelty score (0.0-1.0) required to consider content novel.
                             Default 0.30 means 30% novelty required.
        """
        self.client = OpenAI()
        self.web_config = WebConfigManager()
        self.embedding_model = self.web_config.get_setting(
            "topic_evolution", "embedding_model", "text-embedding-3-small"
        )
        self.novelty_threshold = novelty_threshold

    def calculate_novelty_score(
        self,
        current_topic: Dict,
        recent_topics: List[Dict]
    ) -> Tuple[float, Optional[int]]:
        """
        Calculate novelty score for a topic compared to recent versions.

        Args:
            current_topic: {topic_slug, topic_name, key_points: [str]}
            recent_topics: List of recent topics with same structure

        Returns:
            Tuple of (novelty_score, parent_topic_id)
            - novelty_score: 0.0-1.0 (1.0 = completely novel, 0.0 = identical)
            - parent_topic_id: ID of most similar recent topic, or None
        """
        current_slug = current_topic.get('topic_slug')

        # Find recent topics with matching slug
        matching_topics = [
            t for t in recent_topics
            if t.get('topic_slug') == current_slug
        ]

        if not matching_topics:
            # Completely new topic
            logger.info(f"Topic '{current_topic.get('topic_name')}' is completely new (no matching slug)")
            return 1.0, None

        # Get embeddings for current topic key points
        current_text = " ".join(current_topic.get('key_points', []))
        if not current_text.strip():
            logger.warning(f"Empty key points for topic '{current_topic.get('topic_name')}'")
            return 1.0, None

        try:
            current_embedding = self._get_embedding(current_text)
        except Exception as e:
            logger.error(f"Failed to get embedding for current topic: {e}")
            return 1.0, None  # Assume novel on error

        # Find most similar recent topic
        max_similarity = 0.0
        most_similar_id = None

        for recent_topic in matching_topics:
            recent_text = " ".join(recent_topic.get('key_points', []))
            if not recent_text.strip():
                continue

            try:
                recent_embedding = self._get_embedding(recent_text)
            except Exception as e:
                logger.warning(f"Failed to get embedding for recent topic {recent_topic.get('id')}: {e}")
                continue

            # Calculate cosine similarity
            similarity = self._cosine_similarity(current_embedding, recent_embedding)

            if similarity > max_similarity:
                max_similarity = similarity
                most_similar_id = recent_topic.get('id')

        # Novelty score is inverse of similarity
        novelty_score = 1.0 - max_similarity

        logger.info(
            f"Novelty for '{current_topic.get('topic_name')}': "
            f"{novelty_score:.2f} (similarity: {max_similarity:.2f}, parent_id: {most_similar_id})"
        )

        return novelty_score, most_similar_id

    def is_novel(self, novelty_score: float) -> bool:
        """Check if novelty score meets threshold"""
        return novelty_score >= self.novelty_threshold

    def _get_embedding(self, text: str) -> np.ndarray:
        """Get embedding vector for text"""
        try:
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return np.array(response.data[0].embedding)
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise  # Re-raise for caller to handle

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            logger.warning("Zero vector encountered in similarity calculation")
            return 0.0

        return float(dot_product / (norm1 * norm2))


def get_novelty_detector(novelty_threshold: float = 0.30) -> NoveltyDetector:
    """Factory function to create NoveltyDetector instance"""
    return NoveltyDetector(novelty_threshold=novelty_threshold)
