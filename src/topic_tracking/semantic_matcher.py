"""
SemanticTopicMatcher: Finds semantically similar topics using embedding similarity.
Uses text-embedding-3-small for cost-effective comparisons.
Implements story arc recognition and duplicate detection.
"""

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from openai import OpenAI
import numpy as np

from src.config.web_config import WebConfigManager, SettingsKeys


logger = logging.getLogger(__name__)


@dataclass
class TopicMatch:
    """Result of a semantic topic match"""
    topic_id: int
    topic_name: str
    topic_slug: str
    similarity: float
    key_points: List[str]


class SemanticTopicMatcher:
    """
    Finds semantically similar topics using embedding similarity.
    Uses configurable embedding model for cost-effective comparisons.
    """

    def __init__(self, similarity_threshold: float = 0.85):
        """
        Initialize SemanticTopicMatcher.

        Args:
            similarity_threshold: Consider topics as duplicates if similarity >= threshold.
                                 Default 0.85 = 85% similar means same topic.
        """
        self.client = OpenAI()
        self.web_config = WebConfigManager()
        self.embedding_model = self.web_config.get_setting(
            SettingsKeys.TopicEvolution.CATEGORY, SettingsKeys.TopicEvolution.EMBEDDING_MODEL, "text-embedding-3-small"
        )
        self.similarity_threshold = similarity_threshold
        self._embedding_cache: Dict[str, np.ndarray] = {}

    def find_matching_topic(
        self,
        new_topic_name: str,
        new_key_points: List[str],
        existing_topics: List[Dict],
        digest_topic: str = None
    ) -> Optional[TopicMatch]:
        """
        Find best matching existing topic for a new topic.

        Args:
            new_topic_name: Name of the new topic
            new_key_points: Key points for the new topic
            existing_topics: List of existing topics with id, topic_name, topic_slug, key_points
            digest_topic: Optional filter by parent topic

        Returns:
            TopicMatch if similarity >= threshold, None otherwise
        """
        if not existing_topics:
            return None

        # Filter by digest_topic if provided
        if digest_topic:
            existing_topics = [
                t for t in existing_topics
                if t.get('digest_topic') == digest_topic
            ]

        if not existing_topics:
            return None

        # Create text representation for new topic
        new_text = self._create_topic_text(new_topic_name, new_key_points)

        try:
            new_embedding = self._get_embedding(new_text)
        except Exception as e:
            logger.error(f"Failed to get embedding for new topic '{new_topic_name}': {e}")
            return None

        # Find most similar existing topic
        best_match: Optional[TopicMatch] = None
        best_similarity = 0.0

        for existing in existing_topics:
            existing_text = self._create_topic_text(
                existing.get('topic_name', ''),
                existing.get('key_points', [])
            )

            if not existing_text.strip():
                continue

            try:
                existing_embedding = self._get_embedding(existing_text)
            except Exception as e:
                logger.warning(f"Failed to get embedding for topic {existing.get('id')}: {e}")
                continue

            similarity = self._cosine_similarity(new_embedding, existing_embedding)

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = TopicMatch(
                    topic_id=existing.get('id'),
                    topic_name=existing.get('topic_name', ''),
                    topic_slug=existing.get('topic_slug', ''),
                    similarity=similarity,
                    key_points=existing.get('key_points', [])
                )

        # Return match only if above threshold
        if best_match and best_similarity >= self.similarity_threshold:
            logger.info(
                f"Semantic match found: '{new_topic_name}' matches '{best_match.topic_name}' "
                f"(similarity: {best_similarity:.2f})"
            )
            return best_match

        logger.debug(
            f"No semantic match for '{new_topic_name}' "
            f"(best similarity: {best_similarity:.2f} < threshold {self.similarity_threshold})"
        )
        return None

    def find_duplicate_groups(
        self,
        topics: List[Dict],
        similarity_threshold: float = None
    ) -> List[List[Dict]]:
        """
        Find groups of duplicate topics using union-find algorithm.

        Args:
            topics: List of topic dictionaries with id, topic_name, key_points
            similarity_threshold: Override instance threshold if provided

        Returns:
            List of groups, each group is a list of similar topics sorted by age (oldest first)
        """
        if not topics:
            return []

        threshold = similarity_threshold or self.similarity_threshold

        # Get embeddings for all topics
        embeddings: Dict[int, np.ndarray] = {}
        for topic in topics:
            topic_id = topic.get('id')
            text = self._create_topic_text(
                topic.get('topic_name', ''),
                topic.get('key_points', [])
            )
            if text.strip():
                try:
                    embeddings[topic_id] = self._get_embedding(text)
                except Exception as e:
                    logger.warning(f"Failed to get embedding for topic {topic_id}: {e}")

        # Union-find data structure
        parent = {t['id']: t['id'] for t in topics if t.get('id') in embeddings}

        def find(x):
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        # Compare all pairs and union similar topics
        topic_ids = list(embeddings.keys())
        for i, id1 in enumerate(topic_ids):
            for id2 in topic_ids[i + 1:]:
                similarity = self._cosine_similarity(embeddings[id1], embeddings[id2])
                if similarity >= threshold:
                    union(id1, id2)

        # Group topics by their root parent
        groups: Dict[int, List[Dict]] = {}
        topic_by_id = {t['id']: t for t in topics if t.get('id') in embeddings}

        for topic_id in topic_ids:
            root = find(topic_id)
            if root not in groups:
                groups[root] = []
            groups[root].append(topic_by_id[topic_id])

        # Filter to groups with more than one topic and sort by age
        result = []
        for group in groups.values():
            if len(group) > 1:
                # Sort by first_mentioned_at (oldest first)
                group.sort(key=lambda t: t.get('first_mentioned_at') or t.get('created_at') or '')
                result.append(group)

        logger.info(f"Found {len(result)} duplicate groups from {len(topics)} topics")
        return result

    def get_topic_names_for_prompt(
        self,
        existing_topics: List[Dict],
        max_topics: int = 50
    ) -> str:
        """
        Generate formatted list of existing topic names for GPT prompt.
        Dedupes by slug and returns most recent unique names.

        Args:
            existing_topics: List of topic dictionaries
            max_topics: Maximum number of topics to include

        Returns:
            Formatted string of topic names for prompt inclusion
        """
        if not existing_topics:
            return ""

        # Dedupe by slug, keeping most recent
        seen_slugs: Dict[str, Dict] = {}
        for topic in existing_topics:
            slug = topic.get('topic_slug', '')
            if slug and (slug not in seen_slugs or
                        (topic.get('last_mentioned_at', '') >
                         seen_slugs[slug].get('last_mentioned_at', ''))):
                seen_slugs[slug] = topic

        # Sort by last_mentioned_at and take top N
        unique_topics = sorted(
            seen_slugs.values(),
            key=lambda t: t.get('last_mentioned_at', ''),
            reverse=True
        )[:max_topics]

        # Format as bullet list
        names = [f"- {t.get('topic_name', '')}" for t in unique_topics if t.get('topic_name')]
        return "\n".join(names)

    def get_active_story_arcs_for_prompt(
        self,
        existing_topics: List[Dict],
        story_arc_topics: Dict[str, List[Dict]],
        max_arcs: int = 10
    ) -> str:
        """
        Generate formatted story arcs section for GPT prompt.

        Args:
            existing_topics: All existing topics
            story_arc_topics: Dict mapping arc_id to list of topics in that arc
            max_arcs: Maximum number of arcs to include

        Returns:
            Formatted string describing active story arcs
        """
        if not story_arc_topics:
            return ""

        lines = []
        arcs_included = 0

        for arc_id, arc_topics in story_arc_topics.items():
            if arcs_included >= max_arcs:
                break

            if not arc_topics:
                continue

            # Find canonical topic (oldest)
            arc_topics_sorted = sorted(
                arc_topics,
                key=lambda t: t.get('first_mentioned_at') or t.get('created_at') or ''
            )
            canonical = arc_topics_sorted[0]

            # Collect all unique key points from all topics in arc
            all_key_points = []
            for topic in arc_topics_sorted:
                for kp in topic.get('key_points', []):
                    if kp not in all_key_points:
                        all_key_points.append(kp)

            # Limit to 6 key points
            key_points = all_key_points[:6]

            lines.append(f"\nStory: {canonical.get('topic_name', arc_id)}")
            lines.append(f"Current topic: \"{canonical.get('topic_name', '')}\"")
            lines.append("Key points so far:")
            for kp in key_points:
                lines.append(f"- {kp}")

            arcs_included += 1

        if not lines:
            return ""

        return "\n".join(lines)

    def merge_key_points(
        self,
        existing_key_points: List[str],
        new_key_points: List[str],
        max_points: int = 6
    ) -> List[str]:
        """
        Merge key points from new topic into existing, avoiding duplicates.

        Args:
            existing_key_points: Current key points
            new_key_points: New key points to potentially add
            max_points: Maximum total key points

        Returns:
            Merged list of key points
        """
        merged = list(existing_key_points)

        for new_point in new_key_points:
            if len(merged) >= max_points:
                break

            # Check if semantically similar point exists
            is_duplicate = False
            for existing_point in merged:
                # Simple check: if significant overlap in words, consider duplicate
                new_words = set(new_point.lower().split())
                existing_words = set(existing_point.lower().split())
                overlap = len(new_words & existing_words)
                min_len = min(len(new_words), len(existing_words))

                if min_len > 0 and overlap / min_len > 0.7:
                    is_duplicate = True
                    break

            if not is_duplicate:
                merged.append(new_point)

        return merged[:max_points]

    def _create_topic_text(self, topic_name: str, key_points: List[str]) -> str:
        """Create text representation for embedding"""
        points_text = " ".join(key_points) if key_points else ""
        return f"{topic_name} {points_text}".strip()

    def _get_embedding(self, text: str) -> np.ndarray:
        """Get embedding vector for text, with caching"""
        # Use cache to avoid redundant API calls
        cache_key = text[:500]  # Truncate for cache key
        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]

        response = self.client.embeddings.create(
            model=self.embedding_model,
            input=text
        )
        embedding = np.array(response.data[0].embedding)

        # Cache (limit cache size)
        if len(self._embedding_cache) < 1000:
            self._embedding_cache[cache_key] = embedding

        return embedding

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def clear_cache(self):
        """Clear the embedding cache"""
        self._embedding_cache.clear()


def get_semantic_matcher(similarity_threshold: float = 0.85) -> SemanticTopicMatcher:
    """Factory function to create SemanticTopicMatcher instance"""
    return SemanticTopicMatcher(similarity_threshold=similarity_threshold)
