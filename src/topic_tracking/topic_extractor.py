"""
StoryArcExtractor: Extracts story arcs from episode transcripts using GPT.

Story arcs are evolving narratives that track news stories over time.
Each episode may introduce new story arcs or add events to existing ones.

Key features:
- LLM-driven story arc recognition (no hardcoded keywords)
- Multiple perspectives from different feeds captured as events
- Timeline tracking shows story evolution
- Functional category classification for organization
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional

from openai import OpenAI

from src.config.web_config import WebConfigManager, SettingsKeys
from src.database.story_arc_repo import get_story_arc_repo

# Environment variables expected to be loaded by calling script via src.config.env

logger = logging.getLogger(__name__)

# Functional categories for story arc classification
FUNCTIONAL_CATEGORIES = [
    "model_release",      # New model announcements, updates, versions
    "company_strategy",   # Business moves, pivots, leadership changes
    "research",           # Papers, studies, breakthroughs
    "regulation",         # Policy, legal, governance
    "product_launch",     # New products, features, services
    "partnership",        # Collaborations, acquisitions, investments
    "controversy",        # Disputes, criticisms, debates
    "industry_trend",     # Broader patterns, market shifts
    "technique",          # New methods, approaches, architectures
    "use_case",           # Applications, implementations
    "other"               # Miscellaneous
]


class StoryArcExtractor:
    """
    Extracts and tracks story arcs from episode transcripts.

    Story arcs are ongoing narratives (e.g., "OpenAI's GPT-5 Development")
    that evolve over time with events from multiple sources.
    """

    def __init__(
        self,
        max_arcs_per_episode: int = 3,
    ):
        """
        Initialize StoryArcExtractor.

        Args:
            max_arcs_per_episode: Maximum story arcs to extract per episode
        """
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        # Get settings from web_config first
        try:
            self.web_config = WebConfigManager()
            openai_timeout = self.web_config.get_setting(
                SettingsKeys.ApiTimeouts.CATEGORY, SettingsKeys.ApiTimeouts.OPENAI_TIMEOUT, 120
            )
            self.max_story_arcs_context = self.web_config.get_setting(
                SettingsKeys.Discovery.CATEGORY, SettingsKeys.Discovery.MAX_STORY_ARCS_CONTEXT, 20
            )
            self.model = self.web_config.get_setting(
                SettingsKeys.TopicTracking.CATEGORY, SettingsKeys.TopicTracking.EXTRACTION_MODEL, 'gpt-5-mini'
            )
            logger.info(f"Using extraction model: {self.model}")
        except Exception as e:
            openai_timeout = 120
            self.max_story_arcs_context = 20
            self.model = "gpt-5-mini"
            self.web_config = None
            logger.warning(f"Failed to get settings from web_config, using defaults: {e}")

        self.client = OpenAI(api_key=api_key, timeout=float(openai_timeout))
        self.repo = get_story_arc_repo()
        self.max_arcs_per_episode = max_arcs_per_episode

    def _get_token_param_name(self) -> str:
        """
        Get the correct token parameter name based on model.

        GPT-5+ models use 'max_completion_tokens' instead of 'max_tokens'.
        """
        if self.model.startswith("gpt-5"):
            return "max_completion_tokens"
        return "max_tokens"

    def extract_and_store_story_arcs(
        self,
        episode_id: int,
        episode_guid: str,
        feed_id: int,
        digest_topic: str,
        transcript: str,
        episode_title: str,
        episode_published_date: datetime,
        relevance_score: float = 0.0,
    ) -> List[Dict]:
        """
        Extract story arcs from transcript and store in database.

        The LLM receives context about active story arcs and decides:
        1. Which existing arcs this content continues
        2. What new arcs this content introduces

        Args:
            episode_id: Episode database ID
            episode_guid: Episode GUID
            feed_id: Source feed ID
            digest_topic: Parent topic (e.g., "AI and Technology")
            transcript: Full episode transcript
            episode_title: Episode title (for source attribution)
            episode_published_date: When episode was published
            relevance_score: Episode's relevance score

        Returns:
            List of story arc results (new arcs and events added)
        """
        logger.info(
            f"Extracting story arcs from episode {episode_guid} for {digest_topic}"
        )

        # Get active story arcs for context
        active_arcs_context = ""
        try:
            active_arcs_context = self.repo.get_story_arcs_for_prompt(
                digest_topic=digest_topic,
                max_arcs=self.max_story_arcs_context,
                max_events_per_arc=4
            )
            arc_count = active_arcs_context.count("STORY ARC") if active_arcs_context else 0
            logger.info(f"Retrieved {arc_count} active story arcs for context")
        except Exception as e:
            logger.warning(f"Failed to retrieve active story arcs: {e}")

        # Create prompt for GPT
        prompt = self._create_extraction_prompt(
            transcript=transcript,
            digest_topic=digest_topic,
            active_arcs_context=active_arcs_context,
            episode_title=episode_title
        )
        schema = self._create_extraction_schema()

        try:
            # Build kwargs with model-appropriate token parameter
            api_kwargs = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "story_arc_extraction",
                        "schema": schema,
                        "strict": True,
                    },
                },
                self._get_token_param_name(): 16000,
            }
            response = self.client.chat.completions.create(**api_kwargs)

            # Parse response
            extraction_data = json.loads(response.choices[0].message.content)

            # Process continuing arcs (updates to existing stories)
            continuing_arcs = extraction_data.get("continuing_arcs", [])
            new_arcs = extraction_data.get("new_arcs", [])

            logger.info(
                f"Extracted {len(continuing_arcs)} continuing arcs, "
                f"{len(new_arcs)} new arcs from {episode_guid}"
            )

            results = []

            # Handle continuing arcs (add events to existing stories)
            for arc_data in continuing_arcs[:self.max_arcs_per_episode]:
                try:
                    arc_name = arc_data["arc_name"]
                    event_summary = arc_data["event_summary"]
                    key_points = arc_data.get("key_points", [])
                    perspective = arc_data.get("perspective")
                    category = arc_data.get("category", "other")

                    # Find or get the existing arc
                    arc = self.repo.get_or_create_story_arc(
                        arc_name=arc_name,
                        digest_topic=digest_topic,
                        functional_category=category
                    )

                    # Add the new event
                    event = self.repo.add_story_arc_event(
                        story_arc_id=arc['id'],
                        event_date=episode_published_date,
                        event_summary=event_summary,
                        key_points=key_points,
                        source_feed_id=feed_id,
                        source_episode_id=episode_id,
                        source_episode_guid=episode_guid,
                        source_name=episode_title,
                        perspective=perspective,
                        relevance_score=relevance_score
                    )

                    results.append({
                        "arc_name": arc_name,
                        "arc_id": arc['id'],
                        "is_new": False,
                        "event_id": event['id'],
                        "event_summary": event_summary
                    })

                    logger.info(
                        f"Added event to story arc '{arc_name}' (id={arc['id']})"
                    )

                except Exception as e:
                    logger.warning(
                        f"Failed to add event to arc '{arc_data.get('arc_name', 'unknown')}': {e}"
                    )

            # Handle new arcs (create new stories)
            for arc_data in new_arcs[:self.max_arcs_per_episode - len(results)]:
                try:
                    arc_name = arc_data["arc_name"]
                    event_summary = arc_data["event_summary"]
                    key_points = arc_data.get("key_points", [])
                    category = arc_data.get("category", "other")
                    perspective = arc_data.get("perspective")

                    # Create the arc with initial event
                    arc = self.repo.create_story_arc(
                        arc_name=arc_name,
                        digest_topic=digest_topic,
                        functional_category=category,
                        initial_event={
                            "event_date": episode_published_date,
                            "event_summary": event_summary,
                            "key_points": key_points,
                            "source_feed_id": feed_id,
                            "source_episode_id": episode_id,
                            "source_episode_guid": episode_guid,
                            "source_name": episode_title,
                            "perspective": perspective,
                            "relevance_score": relevance_score
                        }
                    )

                    results.append({
                        "arc_name": arc_name,
                        "arc_id": arc['id'],
                        "is_new": True,
                        "category": category,
                        "event_summary": event_summary
                    })

                    logger.info(
                        f"Created new story arc '{arc_name}' (id={arc['id']}, category={category})"
                    )

                except Exception as e:
                    logger.warning(
                        f"Failed to create arc '{arc_data.get('arc_name', 'unknown')}': {e}"
                    )

            logger.info(
                f"Episode {episode_guid}: {len([r for r in results if r['is_new']])} new arcs, "
                f"{len([r for r in results if not r['is_new']])} arcs updated"
            )

            return results

        except Exception as e:
            logger.error(f"Story arc extraction failed for {episode_guid}: {e}")
            raise

    def _create_extraction_prompt(
        self,
        transcript: str,
        digest_topic: str,
        active_arcs_context: str,
        episode_title: str
    ) -> str:
        """
        Create GPT prompt for story arc extraction.

        Args:
            transcript: Episode transcript
            digest_topic: Parent topic name
            active_arcs_context: Formatted active story arcs
            episode_title: Episode title for context

        Returns:
            Formatted prompt string
        """
        # Truncate transcript to reasonable length
        truncated_transcript = transcript[:6000]

        active_arcs_section = ""
        if active_arcs_context:
            active_arcs_section = f"""
## ACTIVE STORY ARCS
The following stories are currently being tracked. If this episode discusses any of these stories,
you should add a NEW EVENT to that story arc rather than creating a duplicate.

{active_arcs_context}

---
"""

        return f"""Analyze this podcast episode transcript and identify STORY ARCS related to "{digest_topic}".

A STORY ARC is an ongoing news narrative that evolves over time. Examples:
- "OpenAI's GPT-5 Development" (tracks rumors -> announcements -> release -> reactions)
- "EU AI Act Implementation" (tracks drafts -> votes -> enforcement -> industry response)
- "Google Gemini Launch" (tracks leaks -> announcement -> reviews -> updates)

{active_arcs_section}

## YOUR TASK

For this episode from "{episode_title}", identify:

1. **CONTINUING ARCS**: Stories from the active list above that this episode discusses
   - Add a NEW EVENT capturing what this episode says about the story
   - Capture the episode's PERSPECTIVE (positive, negative, neutral, analytical)
   - Include 2-3 specific key points from this episode
   - BE GENEROUS with matching - if content is thematically related to an existing arc, add to it

2. **NEW ARCS**: New stories not in the active list
   - ONLY create if ALL of these conditions are met:
     a) This is a MAJOR breaking news story (not routine coverage)
     b) It involves a specific entity or event (not a general trend)
     c) You are confident it will appear in future episodes
     d) No existing arc covers this topic even tangentially
   - NEW ARCS SHOULD BE RARE - most episodes should have 0 new arcs

## CRITICAL GUIDELINES - READ CAREFULLY

### RULE 1: ALMOST NEVER CREATE NEW ARCS
- **Default behavior: Add events to existing arcs, return empty new_arcs array**
- Creating a new arc should be EXCEPTIONAL - maybe 1 in every 5-10 episodes
- If you're unsure whether to create a new arc, DON'T - add to the most relevant existing arc instead

### RULE 2: BE AGGRESSIVE ABOUT MATCHING EXISTING ARCS
- Look for THEMATIC overlap, not just exact topic matches
- "AI coding assistant update" → add to existing "Coding Agents" or "Claude Code" arc
- "Company announces new monetization" → add to existing monetization/ads arc
- "Researcher discusses capability gaps" → add to existing "Adoption Gap" arc
- When multiple arcs could apply, pick the one with the most events

### RULE 3: DO NOT CREATE ARCS FOR
- General industry trends or discussions (too broad)
- One-off mentions of products or companies (not a story)
- Topics that are variations of existing arcs
- Anything that could reasonably be added to an existing arc
- Speculative or theoretical discussions

### RULE 4: MAXIMUM LIMITS
- Maximum 2 continuing arc events per episode (pick the most significant)
- Maximum 1 new arc per episode (and prefer 0)
- Total maximum 3 story arcs per episode

### RULE 5: NAME MATCHING
When adding to a continuing arc, use the EXACT arc name from the active list.
Do not create slight variations like "OpenAI Ads" vs "OpenAI Advertising" - use the existing name.

## CLASSIFICATION CATEGORIES
Use one of these for each arc:
- model_release: New model announcements, updates, versions
- company_strategy: Business moves, pivots, leadership changes
- research: Papers, studies, breakthroughs
- regulation: Policy, legal, governance
- product_launch: New products, features, services
- partnership: Collaborations, acquisitions, investments
- controversy: Disputes, criticisms, debates
- industry_trend: Broader patterns, market shifts
- technique: New methods, approaches, architectures
- use_case: Applications, implementations
- other: Miscellaneous

## PERSPECTIVE VALUES
- positive: Episode is enthusiastic/supportive about this development
- negative: Episode is critical/concerned about this development
- neutral: Episode presents factual coverage without strong stance
- analytical: Episode provides in-depth analysis/comparison

## TRANSCRIPT
{truncated_transcript}

---
Identify story arcs and events from this episode."""

    def _create_extraction_schema(self) -> dict:
        """
        JSON schema for structured story arc extraction.

        Returns:
            JSON schema dictionary
        """
        arc_event_schema = {
            "type": "object",
            "properties": {
                "arc_name": {
                    "type": "string",
                    "description": "Name of the story arc (use existing name if continuing)"
                },
                "event_summary": {
                    "type": "string",
                    "description": "1-2 sentence summary of what this episode says about the story"
                },
                "key_points": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 4,
                    "description": "Specific details from this episode"
                },
                "category": {
                    "type": "string",
                    "enum": FUNCTIONAL_CATEGORIES,
                    "description": "Functional category of the story"
                },
                "perspective": {
                    "type": "string",
                    "enum": ["positive", "negative", "neutral", "analytical"],
                    "description": "Episode's perspective on this story"
                }
            },
            "required": ["arc_name", "event_summary", "key_points", "category", "perspective"],
            "additionalProperties": False
        }

        return {
            "type": "object",
            "properties": {
                "continuing_arcs": {
                    "type": "array",
                    "items": arc_event_schema,
                    "description": "Events for existing story arcs"
                },
                "new_arcs": {
                    "type": "array",
                    "items": arc_event_schema,
                    "description": "New story arcs introduced by this episode"
                }
            },
            "required": ["continuing_arcs", "new_arcs"],
            "additionalProperties": False
        }


# Backwards compatibility alias
class TopicExtractor(StoryArcExtractor):
    """
    Backwards-compatible alias for StoryArcExtractor.

    The old TopicExtractor extracted topics; the new StoryArcExtractor
    extracts story arcs. This alias allows existing code to work.
    """

    def __init__(
        self,
        max_topics: int = 15,
        novelty_threshold: float = 0.30,
        enable_novelty_detection: bool = True,
        semantic_similarity_threshold: float = 0.80
    ):
        # Ignore old parameters, use new defaults
        super().__init__(
            max_arcs_per_episode=max_topics
        )
        logger.info(
            "TopicExtractor is now StoryArcExtractor - "
            "novelty_threshold and semantic_similarity_threshold are no longer used"
        )

    def extract_and_store_topics(
        self,
        episode_guid: str,
        digest_topic: str,
        transcript: str,
        relevance_score: float,
    ) -> List[Dict]:
        """
        Backwards-compatible wrapper for extract_and_store_story_arcs.

        Note: This requires feed_id, episode_title, and episode_published_date
        which the old API didn't have. We'll try to get them from the database.
        """
        from src.database.models import get_episode_repo

        # Try to get episode details from database
        episode_repo = get_episode_repo()
        try:
            episode = episode_repo.get_by_episode_guid(episode_guid)
            if episode:
                episode_id = episode.id
                feed_id = episode.feed_id
                episode_title = episode.title
                episode_published_date = episode.published_date
            else:
                logger.warning(f"Episode not found: {episode_guid}")
                return []
        except Exception as e:
            logger.warning(f"Failed to get episode details: {e}")
            return []

        # Call the new method
        results = self.extract_and_store_story_arcs(
            episode_id=episode_id,
            episode_guid=episode_guid,
            feed_id=feed_id,
            digest_topic=digest_topic,
            transcript=transcript,
            episode_title=episode_title,
            episode_published_date=episode_published_date,
            relevance_score=relevance_score
        )

        # Convert results to old format for compatibility
        return [
            {
                "name": r.get("arc_name"),
                "type": r.get("category", "other"),
                "key_points": [],  # Events don't have key_points in the same way
                "novelty_score": 1.0 if r.get("is_new") else 0.5,
                "matched_existing": not r.get("is_new"),
                "story_arc": r.get("arc_name")
            }
            for r in results
        ]
