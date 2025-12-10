"""
TopicExtractor: Extracts high-level topics from episode transcripts using GPT.
Used for topic tracking and deduplication in digest generation.
"""

import os
import json
import logging
from typing import List, Dict
from openai import OpenAI

from src.config.web_config import WebConfigManager
from src.database.models import get_episode_repo
from src.database.topic_tracking_repo import get_topic_tracking_repo
from src.topic_tracking.novelty_detector import NoveltyDetector


logger = logging.getLogger(__name__)


class TopicExtractor:
    """
    Extracts high-level topics and key points from episode transcripts.
    Uses GPT-4o-mini for cost-effective topic analysis.
    """

    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.web_config = WebConfigManager()
        self.episode_repo = get_episode_repo()
        self.topic_tracking_repo = get_topic_tracking_repo()

        # Load configuration
        self.max_topics = self.web_config.get_setting(
            "topic_tracking", "max_topics_per_episode", 15
        )
        self.model = "gpt-4o-mini"  # Cost-effective for extraction

        # Initialize novelty detector (v2.01+)
        try:
            novelty_threshold = self.web_config.get_setting(
                "topic_evolution", "novelty_threshold", 0.30
            )
            self.novelty_detector = NoveltyDetector(novelty_threshold=novelty_threshold)
            self.novelty_detection_enabled = self.web_config.get_setting(
                "topic_evolution", "enable_novelty_detection", True
            )
            logger.info(f"Novelty detection enabled: {self.novelty_detection_enabled}, threshold: {novelty_threshold}")
        except Exception as e:
            logger.warning(f"Failed to initialize novelty detector: {e}")
            self.novelty_detector = None
            self.novelty_detection_enabled = False

    def extract_and_store_topics(
        self,
        episode_guid: str,
        digest_topic: str,
        transcript: str,
        relevance_score: float,
    ) -> List[Dict]:
        """
        Extract high-level topics from transcript and store in database.

        Args:
            episode_guid: Episode GUID
            digest_topic: Parent topic (e.g., "AI and Technology")
            transcript: Full episode transcript
            relevance_score: Episode's score for digest_topic

        Returns:
            List of extracted topic dictionaries

        Raises:
            ValueError: If episode not found
            Exception: If extraction fails
        """
        # Get episode ID
        episode = self.episode_repo.get_by_episode_guid(episode_guid)
        if not episode:
            raise ValueError(f"Episode not found: {episode_guid}")

        logger.info(
            f"Extracting topics from episode {episode_guid} for {digest_topic}"
        )

        # Create prompt for GPT
        prompt = self._create_extraction_prompt(transcript, digest_topic)
        schema = self._create_extraction_schema()

        try:
            # Call GPT-4o-mini with structured output
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "topic_extraction",
                        "schema": schema,
                        "strict": True,
                    },
                },
                max_tokens=2000,  # Enough for 15 topics with key points
            )

            # Parse response
            topics_data = json.loads(response.choices[0].message.content)
            extracted_topics = topics_data.get("topics", [])

            logger.info(
                f"Extracted {len(extracted_topics)} topics from episode {episode_guid}"
            )

            # Get recent topics for novelty detection (v2.01+)
            recent_topics = []
            if self.novelty_detection_enabled and self.novelty_detector:
                try:
                    recent_topics = self.topic_tracking_repo.get_topics_last_n_days(
                        digest_topic=digest_topic,
                        days=14,
                        only_used=True
                    )
                    logger.info(f"Retrieved {len(recent_topics)} recent topics for novelty comparison")
                except Exception as e:
                    logger.warning(f"Failed to retrieve recent topics for novelty detection: {e}")

            # Store each topic in database (respect max_topics limit)
            stored_topics = []
            for topic_data in extracted_topics[: self.max_topics]:
                try:
                    # Calculate novelty score (v2.01+)
                    novelty_score = 1.0  # Default: assume novel
                    parent_topic_id = None

                    if self.novelty_detection_enabled and self.novelty_detector and recent_topics:
                        try:
                            novelty_score, parent_topic_id = self.novelty_detector.calculate_novelty_score(
                                current_topic={
                                    'topic_slug': self.topic_tracking_repo._normalize_topic_name(topic_data['name']),
                                    'topic_name': topic_data['name'],
                                    'key_points': topic_data['key_points']
                                },
                                recent_topics=recent_topics
                            )
                        except Exception as e:
                            logger.warning(f"Novelty detection failed for '{topic_data['name']}': {e}")
                            novelty_score = 1.0  # Assume novel on error

                    # Store topic with all fields
                    stored_topic = self.topic_tracking_repo.store_topic(
                        episode_id=episode.id,
                        topic_name=topic_data["name"],
                        key_points=topic_data["key_points"],
                        digest_topic=digest_topic,
                        relevance_score=relevance_score,
                        topic_type=topic_data.get("type", "other"),
                        novelty_score=novelty_score,
                        is_update=topic_data.get("is_update", False),
                        parent_topic_id=parent_topic_id,
                        evolution_summary=topic_data.get("evolution_summary"),
                    )
                    stored_topics.append(
                        {
                            "name": topic_data["name"],
                            "type": topic_data.get("type", "other"),
                            "key_points": topic_data["key_points"],
                            "novelty_score": novelty_score,
                        }
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to store topic '{topic_data['name']}': {e}"
                    )

            # Log if we hit the limit
            if len(extracted_topics) > self.max_topics:
                logger.info(
                    f"Episode {episode_guid} had {len(extracted_topics)} topics, "
                    f"stored top {self.max_topics} (max_topics_per_episode limit)"
                )

            return stored_topics

        except Exception as e:
            logger.error(f"Topic extraction failed for {episode_guid}: {e}")
            raise

    def _create_extraction_prompt(self, transcript: str, digest_topic: str) -> str:
        """
        Create GPT prompt for topic extraction.

        Args:
            transcript: Full episode transcript
            digest_topic: Parent topic name

        Returns:
            Formatted prompt string
        """
        # Truncate transcript to 4000 chars (enough context, saves tokens)
        truncated_transcript = transcript[:4000]

        return f"""Analyze this podcast transcript and extract ALL significant high-level topics discussed that are relevant to "{digest_topic}".

For each topic, provide:
1. **Name**: Clear, specific topic name (e.g., "GPT-5 Multimodal Release", "OpenAI Leadership Crisis")
2. **Type**: Classification from these categories:
   - model_release: New model announcements, updates, versions
   - use_case: Applications, implementations, real-world usage
   - personality: Key people in the news (CEOs, researchers, leaders)
   - research: Papers, studies, breakthroughs
   - company_news: Funding, acquisitions, partnerships, business developments
   - regulation: Policy, legal, governance
   - technique: New methods, approaches, architectures
   - other: Miscellaneous or uncategorized

3. **Key Points**: 2-4 bullet points of key information
4. **Is Update**: Boolean - is this new information about an existing topic?
5. **Related To**: If is_update=true, what's the root topic? (e.g., "gpt-5-release")
6. **Evolution Summary**: If is_update=true, briefly describe what changed/what's new

Instructions:
- Extract EVERY distinct topic, not just the top 1-3
- Focus on newsworthy events, developments, or discussions
- Classify each topic accurately by type
- Mark as update if it builds on/evolves a known topic
- Avoid overly generic topics (e.g., "AI is advancing" is too broad)
- Each topic should be specific enough to track over time

Transcript (first 4000 chars):
{truncated_transcript}

Extract all significant topics with full classification."""

    def _create_extraction_schema(self) -> dict:
        """
        JSON schema for structured topic extraction.

        Returns:
            JSON schema dictionary
        """
        return {
            "type": "object",
            "properties": {
                "topics": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Specific topic name",
                            },
                            "type": {
                                "type": "string",
                                "description": "Topic classification",
                                "enum": [
                                    "model_release",
                                    "use_case",
                                    "personality",
                                    "research",
                                    "company_news",
                                    "regulation",
                                    "technique",
                                    "other",
                                ],
                            },
                            "key_points": {
                                "type": "array",
                                "items": {"type": "string"},
                                "minItems": 2,
                                "maxItems": 4,
                                "description": "Key insights about this topic",
                            },
                            "is_update": {
                                "type": "boolean",
                                "description": "Is this new info about an existing topic?",
                            },
                            "related_to": {
                                "anyOf": [
                                    {"type": "string"},
                                    {"type": "null"}
                                ],
                                "description": "Root topic if this is an update (optional)",
                            },
                            "evolution_summary": {
                                "anyOf": [
                                    {"type": "string"},
                                    {"type": "null"}
                                ],
                                "description": "What changed/what's new if this is an update (optional)",
                            },
                        },
                        "required": ["name", "type", "key_points", "is_update", "related_to", "evolution_summary"],
                        "additionalProperties": False,
                    },
                    "minItems": 1,
                    "maxItems": 15,  # Allow up to 15 topics per episode
                }
            },
            "required": ["topics"],
            "additionalProperties": False,
        }
