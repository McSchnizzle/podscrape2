"""
TopicExtractor: Extracts high-level topics from episode transcripts using GPT.
Used for topic tracking and deduplication in digest generation.

v2.05: Added story arc recognition and semantic matching for topic deduplication.
       Models are now fully configurable via web_settings.
"""

import os
import json
import logging
from typing import List, Dict, Optional

from openai import OpenAI

from src.config.web_config import WebConfigManager
from src.database.models import get_episode_repo
from src.database.topic_tracking_repo import get_topic_tracking_repo
from src.topic_tracking.novelty_detector import NoveltyDetector
from src.topic_tracking.semantic_matcher import SemanticTopicMatcher


logger = logging.getLogger(__name__)


# Story arc patterns - keywords that indicate topics belong to the same evolving story
# These help consolidate related topics like "GPT-5.2 Release Rumors" and "GPT-5.2 Release"
STORY_ARC_PATTERNS = {
    "gemini-3": ["gemini 3", "gemini-3", "gemini3"],
    "gpt-5-release": ["gpt-5", "gpt 5", "gpt5", "gpt-5.2", "gpt 5.2", "gpt-5.1", "gpt 5.1"],
    "openai-strategy": ["openai code red", "openai's focus", "openai's shift", "openai financial"],
    "ai-trust": ["ai trust", "trust in ai", "ai perception", "edelman", "ai sentiment"],
    "google-glasses": ["google glass", "smart glasses", "project aura", "android xr"],
    "cybersecurity-ciso": ["ciso", "cybersecurity", "zero trust", "cyber risk"],
    "ai-benchmarks": ["benchmark", "gdpval", "ai grading", "model performance"],
    "ai-education": ["ai education", "workforce development", "micro-credential", "educational"],
    "social-media-regulation": ["tiktok", "social media ban", "first amendment", "fcc", "media regulation"],
    "streaming-wars": ["netflix", "streaming", "warner bros", "disney acquisition"],
    "claude-release": ["claude 3", "claude 4", "claude-3", "claude-4", "anthropic claude"],
    "llama-release": ["llama 3", "llama 4", "llama-3", "llama-4", "meta llama"],
    "ai-agents": ["ai agent", "ai agents", "autonomous agent", "agent framework"],
    "ai-regulation": ["ai act", "ai regulation", "ai policy", "ai governance", "eu ai"],
}


class TopicExtractor:
    """
    Extracts high-level topics and key points from episode transcripts.
    Model is configurable via web settings (topic_tracking.extraction_model).

    Features (v2.05):
    - Story arc recognition to consolidate related topics
    - Semantic matching to prevent duplicate topic creation
    - Novelty detection to identify new information
    - Configurable models via web_settings
    """

    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.web_config = WebConfigManager()
        self.episode_repo = get_episode_repo()
        self.topic_tracking_repo = get_topic_tracking_repo()

        # Load configuration from web_settings
        self.max_topics = self.web_config.get_setting(
            "topic_tracking", "max_topics_per_episode", 15
        )
        self.model = self.web_config.get_setting(
            "topic_tracking", "extraction_model", "gpt-5-mini"
        )
        self.lookback_days = self.web_config.get_setting(
            "topic_tracking", "retention_days", 30
        )

        # Initialize semantic matcher (v2.05+)
        try:
            similarity_threshold = self.web_config.get_setting(
                "topic_evolution", "similarity_threshold", 0.85
            )
            self.semantic_matcher = SemanticTopicMatcher(
                similarity_threshold=similarity_threshold
            )
            logger.info(f"Semantic matcher initialized with threshold: {similarity_threshold}")
        except Exception as e:
            logger.warning(f"Failed to initialize semantic matcher: {e}")
            self.semantic_matcher = None

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

    def _get_token_param_name(self) -> str:
        """
        Get the correct token parameter name based on model.

        GPT-5.2* models use 'max_completion_tokens' instead of 'max_tokens'
        for the chat.completions API.
        """
        if self.model.startswith("gpt-5.2"):
            return "max_completion_tokens"
        return "max_tokens"

    def extract_and_store_topics(
        self,
        episode_guid: str,
        digest_topic: str,
        transcript: str,
        relevance_score: float,
    ) -> List[Dict]:
        """
        Extract high-level topics from transcript and store in database.

        Implements story arc recognition and semantic matching to prevent
        duplicate topics and consolidate evolving stories.

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

        # Fetch existing topics for context (30 days lookback)
        existing_topics = []
        try:
            existing_topics = self.topic_tracking_repo.get_topics_last_n_days(
                digest_topic=digest_topic,
                days=self.lookback_days,
                only_used=False  # Get all topics, not just used ones
            )
            logger.info(f"Retrieved {len(existing_topics)} existing topics for context")
        except Exception as e:
            logger.warning(f"Failed to retrieve existing topics: {e}")

        # Generate existing topic names for prompt
        existing_topic_names = ""
        if self.semantic_matcher and existing_topics:
            existing_topic_names = self.semantic_matcher.get_topic_names_for_prompt(
                existing_topics, max_topics=50
            )

        # Identify active story arcs
        story_arc_topics = self._get_active_story_arcs(existing_topics)
        active_story_arcs_text = ""
        if self.semantic_matcher and story_arc_topics:
            active_story_arcs_text = self.semantic_matcher.get_active_story_arcs_for_prompt(
                existing_topics, story_arc_topics, max_arcs=10
            )

        # Create prompt with context about existing topics and story arcs
        prompt = self._create_extraction_prompt(
            transcript=transcript,
            digest_topic=digest_topic,
            existing_topic_names=existing_topic_names,
            active_story_arcs=active_story_arcs_text
        )
        schema = self._create_extraction_schema()

        try:
            # Call GPT with structured output
            # Build kwargs with model-appropriate token parameter
            api_kwargs = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "topic_extraction",
                        "schema": schema,
                        "strict": True,
                    },
                },
                self._get_token_param_name(): 2000,  # Enough for 15 topics with key points
            }
            response = self.client.chat.completions.create(**api_kwargs)

            # Parse response
            topics_data = json.loads(response.choices[0].message.content)
            extracted_topics = topics_data.get("topics", [])

            logger.info(
                f"Extracted {len(extracted_topics)} topics from episode {episode_guid}"
            )

            # Get recent topics for novelty detection
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
                    topic_name = topic_data["name"]
                    key_points = topic_data["key_points"]
                    topic_slug = self.topic_tracking_repo._normalize_topic_name(topic_name)

                    # Step 1: Check if this topic belongs to a story arc
                    story_arc_id = self._identify_story_arc(topic_name, key_points)
                    if story_arc_id and story_arc_id in story_arc_topics:
                        # Use the canonical topic from this story arc
                        canonical = story_arc_topics[story_arc_id][0]  # Oldest topic
                        logger.info(
                            f"Topic '{topic_name}' belongs to story arc '{story_arc_id}', "
                            f"extending canonical topic '{canonical.get('topic_name')}'"
                        )
                        # Merge key points
                        merged_key_points = self.semantic_matcher.merge_key_points(
                            canonical.get('key_points', []),
                            key_points,
                            max_points=6
                        ) if self.semantic_matcher else key_points

                        # Update the canonical topic with new key points
                        self.topic_tracking_repo.update_topic_key_points(
                            topic_id=canonical.get('id'),
                            key_points=merged_key_points
                        )

                        stored_topics.append({
                            "name": canonical.get('topic_name'),
                            "type": topic_data.get("type", "other"),
                            "key_points": merged_key_points,
                            "novelty_score": 0.5,  # Partial novelty for story arc update
                            "extended_arc": story_arc_id,
                        })
                        continue

                    # Step 2: Check for semantic match against existing topics
                    matched_topic = None
                    if self.semantic_matcher and existing_topics:
                        matched_topic = self.semantic_matcher.find_matching_topic(
                            new_topic_name=topic_name,
                            new_key_points=key_points,
                            existing_topics=existing_topics,
                            digest_topic=digest_topic
                        )

                    if matched_topic:
                        # Use existing topic's name and slug, merge key points
                        logger.info(
                            f"Semantic match: '{topic_name}' -> '{matched_topic.topic_name}' "
                            f"(similarity: {matched_topic.similarity:.2f})"
                        )
                        merged_key_points = self.semantic_matcher.merge_key_points(
                            matched_topic.key_points,
                            key_points,
                            max_points=6
                        )

                        # Update existing topic with new key points
                        self.topic_tracking_repo.update_topic_key_points(
                            topic_id=matched_topic.topic_id,
                            key_points=merged_key_points
                        )

                        stored_topics.append({
                            "name": matched_topic.topic_name,
                            "type": topic_data.get("type", "other"),
                            "key_points": merged_key_points,
                            "novelty_score": 1.0 - matched_topic.similarity,
                            "matched_existing": True,
                        })
                        continue

                    # Step 3: No match found - create as new topic
                    # Calculate novelty score
                    novelty_score = 1.0  # Default: assume novel
                    parent_topic_id = None

                    if self.novelty_detection_enabled and self.novelty_detector and recent_topics:
                        try:
                            novelty_score, parent_topic_id = self.novelty_detector.calculate_novelty_score(
                                current_topic={
                                    'topic_slug': topic_slug,
                                    'topic_name': topic_name,
                                    'key_points': key_points
                                },
                                recent_topics=recent_topics
                            )
                        except Exception as e:
                            logger.warning(f"Novelty detection failed for '{topic_name}': {e}")
                            novelty_score = 1.0  # Assume novel on error

                    # Store topic with all fields
                    stored_topic = self.topic_tracking_repo.store_topic(
                        episode_id=episode.id,
                        topic_name=topic_name,
                        key_points=key_points,
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
                            "name": topic_name,
                            "type": topic_data.get("type", "other"),
                            "key_points": key_points,
                            "novelty_score": novelty_score,
                        }
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to store topic '{topic_data.get('name', 'unknown')}': {e}"
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

    def _identify_story_arc(
        self, topic_name: str, key_points: List[str] = None
    ) -> Optional[str]:
        """
        Identify which story arc a topic belongs to based on keywords.

        Args:
            topic_name: The topic name to check
            key_points: Optional list of key points for additional context

        Returns:
            Story arc ID if found, None otherwise
        """
        text_to_check = topic_name.lower()
        if key_points:
            text_to_check += " " + " ".join(key_points).lower()

        for arc_id, patterns in STORY_ARC_PATTERNS.items():
            for pattern in patterns:
                if pattern in text_to_check:
                    return arc_id

        return None

    def _get_active_story_arcs(
        self, existing_topics: List[Dict]
    ) -> Dict[str, List[Dict]]:
        """
        Group existing topics by their story arcs.

        Args:
            existing_topics: List of existing topic dictionaries

        Returns:
            Dict mapping arc_id to list of topics in that arc (sorted oldest first)
        """
        story_arcs: Dict[str, List[Dict]] = {}

        for topic in existing_topics:
            arc_id = self._identify_story_arc(
                topic.get('topic_name', ''),
                topic.get('key_points', [])
            )
            if arc_id:
                if arc_id not in story_arcs:
                    story_arcs[arc_id] = []
                story_arcs[arc_id].append(topic)

        # Sort each arc's topics by first_mentioned_at (oldest first)
        for arc_id in story_arcs:
            story_arcs[arc_id].sort(
                key=lambda t: t.get('first_mentioned_at') or t.get('created_at') or ''
            )

        return story_arcs

    def _create_extraction_prompt(
        self,
        transcript: str,
        digest_topic: str,
        existing_topic_names: str = "",
        active_story_arcs: str = ""
    ) -> str:
        """
        Create GPT prompt for topic extraction.

        Args:
            transcript: Full episode transcript
            digest_topic: Parent topic name
            existing_topic_names: Formatted list of existing topic names
            active_story_arcs: Formatted description of active story arcs

        Returns:
            Formatted prompt string
        """
        # Truncate transcript to 4000 chars (enough context, saves tokens)
        truncated_transcript = transcript[:4000]

        # Build prompt sections
        existing_topics_section = ""
        if existing_topic_names:
            existing_topics_section = f"""
IMPORTANT - Existing Topics to Reuse:
The following topics already exist in our database. If any topic in this transcript
matches one of these (even if phrased differently), USE THE EXISTING TOPIC NAME EXACTLY:
{existing_topic_names}

When you find content about an existing topic:
- Use the EXACT existing topic name (don't create a variation)
- Mark is_update=true
- Add only NEW key points not covered before
"""

        story_arcs_section = ""
        if active_story_arcs:
            story_arcs_section = f"""
ACTIVE STORY ARCS:
The following stories are currently being tracked. If this transcript discusses any of these,
you should EXTEND the existing story rather than create a new topic:
{active_story_arcs}

When extending a story arc:
- Use the existing topic name exactly
- Add NEW developments as key points
- Mark is_update=true
"""

        return f"""Analyze this podcast transcript and extract ALL significant high-level topics discussed that are relevant to "{digest_topic}".
{existing_topics_section}
{story_arcs_section}
For each topic, provide:
1. **Name**: Clear, specific topic name (e.g., "GPT-5 Multimodal Release", "OpenAI Leadership Crisis")
   - If the topic matches an existing one above, use the EXACT existing name
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
- PRIORITIZE reusing existing topic names when the content matches
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
