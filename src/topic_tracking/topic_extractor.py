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
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional

from src.config.web_config import WebConfigManager, SettingsKeys
from src.database.story_arc_repo import get_story_arc_repo


def _claude_cli_model() -> str:
    """Alias for `claude -p --model`. Sourced from
    src/config/models.py::MODEL_ROLES so a model change is one edit,
    not eleven. Falls back to the previous literal if the import
    fails, so this can never break the pipeline."""
    try:
        from src.config.models import role
        return role("claude_cli")
    except Exception:
        return "sonnet"


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

        v3.31: migrated from OpenAI gpt-5-mini json_schema mode to claude -p
        with the .claude/commands/extract-story-arcs.md skill. The OpenAI
        path was failing in production with 400 Bad Request errors.
        """
        # web_config is still consulted for the active-arcs context size knob.
        try:
            self.web_config = WebConfigManager()
            self.max_story_arcs_context = self.web_config.get_setting(
                SettingsKeys.Discovery.CATEGORY, SettingsKeys.Discovery.MAX_STORY_ARCS_CONTEXT, 20
            )
        except Exception as e:
            self.max_story_arcs_context = 20
            self.web_config = None
            logger.warning(f"Failed to get settings from web_config, using defaults: {e}")

        self.repo = get_story_arc_repo()
        self.max_arcs_per_episode = max_arcs_per_episode

    @staticmethod
    def _call_claude_p(prompt: str, timeout: int = 240) -> str:
        """Call claude -p with prompt via stdin. Returns trimmed stdout."""
        claude_path = os.path.expanduser("~/.local/bin/claude")
        if not os.path.exists(claude_path):
            claude_path = "claude"
        env = os.environ.copy()
        env.pop("CLAUDECODE", None)
        env.pop("ANTHROPIC_API_KEY", None)  # Force Max subscription, not API billing
        result = subprocess.run(
            [claude_path, "-p", "--model", _claude_cli_model(), "--effort", "medium",
             "--tools", "", "--no-session-persistence", "-"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"claude -p failed (exit {result.returncode}): {result.stderr[:500]}"
            )
        return result.stdout.strip()

    def _load_extraction_skill(self) -> str:
        """Load the story arc extraction skill from .claude/commands/."""
        skill_path = (
            Path(__file__).parent.parent.parent
            / '.claude' / 'commands' / 'extract-story-arcs.md'
        )
        if skill_path.exists():
            return skill_path.read_text()
        # Embedded fallback so et01 works even if skill file isn't deployed.
        return (
            "Extract story arcs from the transcript and return ONLY a JSON "
            "object with `continuing_arcs` and `new_arcs` arrays. Each entry "
            "must have arc_name, event_summary, key_points, category, "
            "perspective. No markdown, no explanation."
        )

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

        # v3.31: skip if claude -p is broken on this host. The pipeline
        # already has graceful degradation for missing arcs (the dedup pass
        # and digest generator both handle empty arc lists).
        try:
            from src.utils.claude_p_health import is_claude_p_healthy
            if not is_claude_p_healthy():
                logger.warning(
                    f"Story arc extraction skipped for {episode_guid}: "
                    f"claude -p unhealthy"
                )
                return []
        except Exception:
            pass

        # Build the claude -p prompt: skill + active arcs + task framing + transcript
        skill_content = self._load_extraction_skill()
        prompt = self._build_claude_p_extraction_prompt(
            skill_content=skill_content,
            transcript=transcript,
            digest_topic=digest_topic,
            active_arcs_context=active_arcs_context,
            episode_title=episode_title,
        )

        try:
            try:
                raw = self._call_claude_p(prompt)
            except subprocess.TimeoutExpired:
                logger.warning(
                    f"Story arc extraction: claude -p timed out for {episode_guid}"
                )
                # Don't poison global health — prompt-specific timeout
                return []

            # Strip markdown code fences defensively
            if raw.startswith('```json'):
                raw = raw.replace('```json', '').replace('```', '').strip()
            elif raw.startswith('```'):
                raw = raw.replace('```', '').strip()

            try:
                extraction_data = json.loads(raw)
            except json.JSONDecodeError as je:
                logger.error(
                    f"Story arc extraction: claude -p returned non-JSON for "
                    f"{episode_guid}: {je}; first 300 chars: {raw[:300]!r}"
                )
                return []

            # Validate top-level shape
            if not isinstance(extraction_data, dict):
                logger.error(
                    f"Story arc extraction: expected dict, got {type(extraction_data).__name__}"
                )
                return []
            if 'continuing_arcs' not in extraction_data:
                extraction_data['continuing_arcs'] = []
            if 'new_arcs' not in extraction_data:
                extraction_data['new_arcs'] = []

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

                    # Auto-generate hot briefing if arc just crossed thresholds (v3.27+)
                    try:
                        from src.topic_tracking.hot_briefing_generator import maybe_generate_hot_briefing
                        refreshed = self.repo.get_story_arc_by_id(arc['id']) or {}
                        maybe_generate_hot_briefing(
                            arc_id=arc['id'],
                            event_count=refreshed.get('event_count') or 0,
                            source_count=refreshed.get('source_count') or 0,
                        )
                    except Exception as e:
                        logger.debug(f"Hot briefing auto-gen skipped: {e}")

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

    def _build_claude_p_extraction_prompt(
        self,
        skill_content: str,
        transcript: str,
        digest_topic: str,
        active_arcs_context: str,
        episode_title: str,
    ) -> str:
        """Build the claude -p prompt: skill + active arcs + task framing + transcript.

        v3.31: replaces the old _create_extraction_prompt + _create_extraction_schema
        pair. The skill file (.claude/commands/extract-story-arcs.md) carries the
        rules, JSON contract, category list, and perspective values. This method
        appends the per-call context (active arcs + episode-specific framing +
        transcript excerpt).
        """
        # Same 6000-char transcript cap as the old extractor
        truncated_transcript = transcript[:6000]

        active_arcs_section = ""
        if active_arcs_context:
            active_arcs_section = (
                "\n## ACTIVE STORY ARCS\n"
                "The following stories are currently being tracked. If this episode "
                "discusses any of these stories, you should add a NEW EVENT to that "
                "story arc rather than creating a duplicate.\n\n"
                f"{active_arcs_context}\n\n---\n"
            )

        return (
            f"{skill_content}\n\n"
            f"---\n\n"
            f"# Input for this run\n\n"
            f"## Parent Topic\n\n"
            f"{digest_topic}\n\n"
            f"## Episode Title\n\n"
            f"{episode_title}\n"
            f"{active_arcs_section}\n"
            f"## Transcript\n\n"
            f"{truncated_transcript}\n\n"
            f"---\n\n"
            f"Now perform the story arc extraction on the transcript above "
            f"and return ONLY the JSON object as specified in the Output Format "
            f"section. No preamble, no questions, no markdown fences."
        )


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
