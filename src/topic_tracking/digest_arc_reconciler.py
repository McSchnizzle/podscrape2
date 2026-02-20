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
from datetime import datetime, timezone
from typing import Dict, List, Optional

from openai import OpenAI

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
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        self.web_config = WebConfigManager()

        self.model = self.web_config.get_setting(
            SettingsKeys.TopicTracking.CATEGORY,
            SettingsKeys.TopicTracking.RECONCILIATION_MODEL,
            'gpt-5-mini'
        )
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

        openai_timeout = self.web_config.get_setting(
            SettingsKeys.ApiTimeouts.CATEGORY,
            SettingsKeys.ApiTimeouts.OPENAI_TIMEOUT,
            120
        )

        self.client = OpenAI(api_key=api_key, timeout=float(openai_timeout))
        self.repo = get_story_arc_repo()
        self.matcher = SemanticTopicMatcher()

        logger.info(
            f"DigestArcReconciler initialized: model={self.model}, "
            f"lookback={self.lookback}, min_occurrences={self.min_occurrences}"
        )

    def _get_token_param_name(self) -> str:
        """Get correct token param name for the model.

        GPT-5+ models use 'max_completion_tokens' instead of 'max_tokens'.
        """
        if self.model.startswith("gpt-5"):
            return "max_completion_tokens"
        return "max_tokens"

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
                    arc = self.repo.create_story_arc(
                        arc_name=story_name,
                        digest_topic=digest_topic,
                        functional_category=category,
                        # No initial_event - reconciler creates arc shells only.
                        # Real events are added when episodes mention the arc.
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
        Use GPT to identify recurring stories across digest scripts.

        Returns list of recurring stories with name, category, occurrences, summary.
        """
        # Build digest summaries for the prompt
        digest_sections = []
        for s in scripts:
            content = s['content'][:4000]  # Trim per digest to fit context
            digest_sections.append(f"--- DIGEST ({s['date']}) ---\n{content}")

        all_digests_text = "\n\n".join(digest_sections)

        prompt = f"""Analyze these {len(scripts)} recent digest scripts for the topic "{digest_topic}".

Your task: Identify RECURRING stories, products, companies, or entities that appear across MULTIPLE digests.

For each recurring story, provide:
- name: A clear, specific name (e.g., "Moltbook AI Laptop", "OpenAI Agents SDK")
- category: One of [model_release, company_strategy, research, regulation, product_launch, partnership, controversy, industry_trend, technique, use_case, other]
- occurrences: How many digests mention this story
- summary: A 1-2 sentence summary of the recurring narrative

CRITICAL RULES:
- Only include stories that appear in {self.min_occurrences}+ different digests
- Be specific: "Moltbook" not "AI hardware developments"
- Focus on concrete entities, products, companies, events - not broad themes
- Maximum 10 recurring stories

{all_digests_text}

Return ONLY recurring stories appearing in {self.min_occurrences}+ digests."""

        schema = {
            "type": "object",
            "properties": {
                "recurring_stories": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "category": {
                                "type": "string",
                                "enum": [
                                    "model_release", "company_strategy", "research",
                                    "regulation", "product_launch", "partnership",
                                    "controversy", "industry_trend", "technique",
                                    "use_case", "other"
                                ]
                            },
                            "occurrences": {"type": "integer"},
                            "summary": {"type": "string"}
                        },
                        "required": ["name", "category", "occurrences", "summary"],
                        "additionalProperties": False
                    }
                }
            },
            "required": ["recurring_stories"],
            "additionalProperties": False
        }

        try:
            api_kwargs = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "recurring_stories_extraction",
                        "schema": schema,
                        "strict": True,
                    },
                },
                self._get_token_param_name(): 16000,
            }
            response = self.client.chat.completions.create(**api_kwargs)
            choice = response.choices[0]
            content = choice.message.content
            if not content:
                logger.warning("GPT returned empty content for recurring stories extraction")
                return []
            data = json.loads(content)
            stories = data.get("recurring_stories", [])

            # Filter by min_occurrences
            stories = [s for s in stories if s.get('occurrences', 0) >= self.min_occurrences]

            return stories

        except Exception as e:
            logger.error(f"Failed to extract recurring stories: {e}")
            return []
