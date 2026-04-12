"""
DigestArcReconciler: Post-digest story arc reconciliation.

Analyzes recent digest scripts to detect recurring stories/products/entities
that appear across multiple digests but haven't been tracked as story arcs.
Creates missing arcs so future digests can reference them for continuity.

The AInewsletter dedup script handles merging duplicate arcs separately.
This reconciler only creates MISSING arcs from recurring digest stories.
"""

import os
import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from src.config.web_config import WebConfigManager, SettingsKeys
from src.database.story_arc_repo import get_story_arc_repo, StoryArcRepository
from src.topic_tracking.semantic_matcher import SemanticTopicMatcher

logger = logging.getLogger(__name__)


class DigestArcReconciler:
    """
    Reconciles story arcs by analyzing recent digest scripts for recurring
    stories not yet tracked as arcs.
    """

    def __init__(self):
        """v3.31: migrated from OpenAI gpt-5-mini json_schema mode to claude -p
        with the .claude/commands/reconcile-recurring-stories.md skill.
        """
        self.web_config = WebConfigManager()

        self.lookback = self.web_config.get_setting(
            SettingsKeys.TopicTracking.CATEGORY,
            SettingsKeys.TopicTracking.RECONCILIATION_LOOKBACK,
            7
        )
        self.min_occurrences = self.web_config.get_setting(
            SettingsKeys.TopicTracking.CATEGORY,
            SettingsKeys.TopicTracking.RECONCILIATION_MIN_OCCURRENCES,
            2
        )

        self.repo = get_story_arc_repo()
        self.matcher = SemanticTopicMatcher()

        logger.info(
            f"DigestArcReconciler initialized: lookback={self.lookback}, "
            f"min_occurrences={self.min_occurrences}"
        )

    @staticmethod
    def _call_claude_p(prompt: str, timeout: int = 240) -> str:
        """Call claude -p with prompt via stdin. Returns trimmed stdout."""
        claude_path = os.path.expanduser("~/.local/bin/claude")
        if not os.path.exists(claude_path):
            claude_path = "claude"
        env = os.environ.copy()
        env.pop("CLAUDECODE", None)
        env.pop("ANTHROPIC_API_KEY", None)
        result = subprocess.run(
            [claude_path, "-p", "--model", "sonnet", "--effort", "medium",
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

    def _load_reconciliation_skill(self) -> str:
        """Load the recurring-stories skill from .claude/commands/."""
        skill_path = (
            Path(__file__).parent.parent.parent
            / '.claude' / 'commands' / 'reconcile-recurring-stories.md'
        )
        if skill_path.exists():
            return skill_path.read_text()
        return (
            "Identify recurring stories across the digest scripts and return "
            "ONLY a JSON object with a `recurring_stories` array. Each entry "
            "must have name, category, occurrences, summary. No markdown."
        )

    def reconcile(self, digest_topic: str, dry_run: bool = False) -> Dict:
        """
        Analyze recent digest scripts for recurring stories and create missing arcs.

        Args:
            digest_topic: Topic to reconcile (e.g., "AI and Technology")
            dry_run: If True, don't write to database, just report findings

        Returns:
            Dict with reconciliation results
        """
        logger.info(f"Starting reconciliation for '{digest_topic}' (dry_run={dry_run})")

        # 1. Query recent digest scripts
        recent_scripts = self._get_recent_digest_scripts(digest_topic)
        if not recent_scripts:
            logger.info(f"No recent digests found for '{digest_topic}'")
            return {
                'arcs_created': 0,
                'arcs_skipped': 0,
                'stories_found': 0,
                'details': [],
                'message': 'No recent digests found'
            }

        logger.info(f"Found {len(recent_scripts)} recent digests for '{digest_topic}'")

        # 2. Extract recurring stories via GPT
        recurring_stories = self._extract_recurring_stories(recent_scripts, digest_topic)
        if not recurring_stories:
            logger.info("No recurring stories detected across digests")
            return {
                'arcs_created': 0,
                'arcs_skipped': 0,
                'stories_found': 0,
                'details': [],
                'message': 'No recurring stories found'
            }

        logger.info(f"Found {len(recurring_stories)} recurring stories")

        # 3. Check each story against existing arcs
        active_arcs = self.repo.get_active_story_arcs(digest_topic, days=14)
        existing_arc_data = [
            {
                'id': arc['id'],
                'topic_name': arc['arc_name'],
                'topic_slug': arc['arc_slug'],
                'key_points': [],
                'digest_topic': arc['digest_topic'],
            }
            for arc in active_arcs
        ]

        arcs_created = 0
        arcs_skipped = 0
        details = []

        for story in recurring_stories:
            story_name = story['name']
            category = story.get('category', 'other')
            occurrences = story.get('occurrences', 0)
            summary = story.get('summary', '')

            # Check semantic match against existing arcs
            match = self.matcher.find_matching_topic(
                new_topic_name=story_name,
                new_key_points=[summary],
                existing_topics=existing_arc_data,
                digest_topic=digest_topic
            )

            if match:
                logger.info(
                    f"Story '{story_name}' matches existing arc '{match.topic_name}' "
                    f"(similarity={match.similarity:.2f}) - skipping"
                )
                arcs_skipped += 1
                details.append({
                    'story': story_name,
                    'action': 'skipped',
                    'reason': f"Matches existing arc '{match.topic_name}' ({match.similarity:.2f})",
                    'occurrences': occurrences
                })
                continue

            # No match - create new arc
            if dry_run:
                logger.info(
                    f"[DRY RUN] Would create arc: '{story_name}' "
                    f"(category={category}, occurrences={occurrences})"
                )
                details.append({
                    'story': story_name,
                    'action': 'would_create',
                    'category': category,
                    'occurrences': occurrences,
                    'summary': summary
                })
                arcs_created += 1
            else:
                try:
                    # v3.27: seed the arc with a synthetic "reconciler" event so
                    # it has event_count>=1 and is eligible for classification.
                    # Prior behavior created empty arc shells that never got
                    # populated and sat with event_count=0 forever.
                    from datetime import datetime as _dt, timezone as _tz
                    seed_event = {
                        "event_date": _dt.now(_tz.utc),
                        "event_summary": summary or f"Recurring story: {story_name}",
                        "key_points": [f"Detected in {occurrences} recent digests"],
                        "source_feed_id": None,
                        "source_episode_id": None,
                        "source_episode_guid": None,
                        "source_name": "digest_arc_reconciler",
                        "perspective": "neutral",
                        "relevance_score": None,
                    }
                    arc = self.repo.create_story_arc(
                        arc_name=story_name,
                        digest_topic=digest_topic,
                        functional_category=category,
                        initial_event=seed_event,
                    )
                    logger.info(
                        f"Created arc: '{story_name}' (id={arc['id']}, "
                        f"category={category}, occurrences={occurrences})"
                    )
                    arcs_created += 1
                    details.append({
                        'story': story_name,
                        'action': 'created',
                        'arc_id': arc['id'],
                        'category': category,
                        'occurrences': occurrences,
                        'summary': summary
                    })

                    # Add to existing_arc_data so subsequent stories don't duplicate
                    existing_arc_data.append({
                        'id': arc['id'],
                        'topic_name': arc['arc_name'],
                        'topic_slug': arc['arc_slug'],
                        'key_points': [summary],
                        'digest_topic': digest_topic,
                    })

                except Exception as e:
                    logger.warning(f"Failed to create arc for '{story_name}': {e}")
                    details.append({
                        'story': story_name,
                        'action': 'error',
                        'error': str(e)
                    })

        result = {
            'arcs_created': arcs_created,
            'arcs_skipped': arcs_skipped,
            'stories_found': len(recurring_stories),
            'details': details,
            'message': f"Reconciled {digest_topic}: {arcs_created} created, {arcs_skipped} skipped"
        }

        logger.info(result['message'])
        return result

    def _get_recent_digest_scripts(self, digest_topic: str) -> List[Dict]:
        """
        Query recent digest scripts from the database.

        Returns list of dicts with 'date' and 'content' keys.
        """
        from src.database.models import get_database_manager
        from src.database.sqlalchemy_models import Digest as DigestModel

        db_manager = get_database_manager()

        with db_manager.get_session() as session:
            digests = session.query(DigestModel).filter(
                DigestModel.topic == digest_topic,
                DigestModel.script_content.isnot(None),
                DigestModel.script_content != ''
            ).order_by(
                DigestModel.digest_date.desc()
            ).limit(self.lookback).all()

            return [
                {
                    'date': d.digest_date.isoformat() if d.digest_date else 'unknown',
                    'content': d.script_content[:8000] if d.script_content else ''
                }
                for d in digests
                if d.script_content
            ]

    def _extract_recurring_stories(
        self, scripts: List[Dict], digest_topic: str
    ) -> List[Dict]:
        """
        Use claude -p to identify recurring stories across digest scripts.

        v3.31: migrated from OpenAI gpt-5-mini json_schema mode to claude -p
        with the .claude/commands/reconcile-recurring-stories.md skill.

        Returns list of recurring stories with name, category, occurrences, summary.
        """
        # Skip if claude -p is broken on this host
        try:
            from src.utils.claude_p_health import is_claude_p_healthy
            if not is_claude_p_healthy():
                logger.warning(
                    "Recurring stories extraction skipped: claude -p unhealthy"
                )
                return []
        except Exception:
            pass

        # Build digest sections (same trim as before)
        digest_sections = []
        for s in scripts:
            content = s['content'][:4000]
            digest_sections.append(f"--- DIGEST ({s['date']}) ---\n{content}")
        all_digests_text = "\n\n".join(digest_sections)

        skill_content = self._load_reconciliation_skill()
        prompt = (
            f"{skill_content}\n\n"
            f"---\n\n"
            f"# Input for this run\n\n"
            f"## Parent Topic\n\n"
            f"{digest_topic}\n\n"
            f"## Minimum occurrences threshold\n\n"
            f"{self.min_occurrences}\n\n"
            f"## Recent digest scripts ({len(scripts)} total)\n\n"
            f"{all_digests_text}\n\n"
            f"---\n\n"
            f"Now identify recurring stories appearing in {self.min_occurrences}+ "
            f"of the digests above and return ONLY the JSON object specified in "
            f"the Output Format section. No preamble, no questions, no markdown fences."
        )

        try:
            try:
                raw = self._call_claude_p(prompt)
            except subprocess.TimeoutExpired:
                logger.warning("Recurring stories: claude -p timed out")
                # Don't poison global health — prompt-specific timeout
                return []

            # Strip markdown fences defensively
            if raw.startswith('```json'):
                raw = raw.replace('```json', '').replace('```', '').strip()
            elif raw.startswith('```'):
                raw = raw.replace('```', '').strip()

            try:
                data = json.loads(raw)
            except json.JSONDecodeError as je:
                logger.error(
                    f"Recurring stories: claude -p returned non-JSON: {je}; "
                    f"first 300 chars: {raw[:300]!r}"
                )
                return []

            if not isinstance(data, dict):
                logger.error(
                    f"Recurring stories: expected dict, got {type(data).__name__}"
                )
                return []

            stories = data.get("recurring_stories", [])
            if not isinstance(stories, list):
                logger.error(
                    f"Recurring stories: 'recurring_stories' is not a list, "
                    f"got {type(stories).__name__}"
                )
                return []

            # Filter by min_occurrences (defensive — the skill is told to do this
            # but we enforce it in code as well)
            stories = [
                s for s in stories
                if isinstance(s, dict) and s.get('occurrences', 0) >= self.min_occurrences
            ]

            return stories

        except Exception as e:
            logger.error(f"Failed to extract recurring stories: {e}")
            return []
