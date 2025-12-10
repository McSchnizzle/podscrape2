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

            # Store each topic in database (respect max_topics limit)
            stored_topics = []
            for topic_data in extracted_topics[: self.max_topics]:
                try:
                    stored_topic = self.topic_tracking_repo.store_topic(
                        episode_id=episode.id,
                        topic_name=topic_data["name"],
                        key_points=topic_data["key_points"],
                        digest_topic=digest_topic,
                        relevance_score=relevance_score,
                    )
                    stored_topics.append(
                        {
                            "name": topic_data["name"],
                            "key_points": topic_data["key_points"],
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

For each topic:
1. Provide a clear, specific topic name (e.g., "OpenAI leadership crisis", "GPT-5 release timeline")
2. List 2-4 key points or insights about that topic

Instructions:
- Extract EVERY distinct topic, not just the top 1-3
- Focus on newsworthy events, developments, or discussions
- Include company news, product releases, policy changes, research findings, industry trends
- Avoid overly generic topics (e.g., "AI is advancing" is too broad)
- Each topic should be specific enough to track over time

Transcript (first 4000 chars):
{truncated_transcript}

Extract all significant topics and their key insights."""

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
                            "key_points": {
                                "type": "array",
                                "items": {"type": "string"},
                                "minItems": 2,
                                "maxItems": 4,
                                "description": "Key insights about this topic",
                            },
                        },
                        "required": ["name", "key_points"],
                        "additionalProperties": False,
                    },
                    "minItems": 1,
                    "maxItems": 15,  # Allow up to 15 topics per episode
                }
            },
            "required": ["topics"],
            "additionalProperties": False,
        }
