#!/usr/bin/env python3
"""
Story Arc Deduplication Phase Script
Consolidates duplicate/similar story arcs using semantic matching.
Ported from AInewsletter's dedupe_topics.py into the podcast pipeline.
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
import argparse
from collections import defaultdict

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

# Set up environment via centralized entry point
from src.utils.phase_bootstrap import bootstrap_phase
bootstrap_phase()

from src.database.models import get_database_manager
from src.database.sqlalchemy_models import StoryArc, StoryArcEvent
from src.utils.logging_config import setup_phase_logging


def resolve_dry_run_flag(cli_flag: bool) -> bool:
    env_value = os.getenv("DRY_RUN")
    if env_value is not None:
        return env_value.strip().lower() in {"1", "true", "yes", "on"}
    return cli_flag


class StoryArcDeduplicator:
    """Consolidates duplicate story arcs using semantic similarity."""

    def __init__(self, dry_run: bool = False, verbose: bool = False,
                 similarity_threshold: float = None):
        self.pipeline_logger = setup_phase_logging("dedup", verbose=verbose, console_output=True)
        self.logger = self.pipeline_logger.get_logger()
        self.dry_run = dry_run
        self.verbose = verbose

        # Load similarity threshold from settings or use default
        if similarity_threshold is None:
            try:
                from src.config.web_config import WebConfigManager, SettingsKeys
                wc = WebConfigManager()
                self.similarity_threshold = float(wc.get_setting(
                    SettingsKeys.TopicEvolution.CATEGORY,
                    SettingsKeys.TopicEvolution.SIMILARITY_THRESHOLD,
                    0.65
                ))
            except Exception:
                self.similarity_threshold = 0.65
        else:
            self.similarity_threshold = similarity_threshold

        self.db_manager = get_database_manager()
        self.logger.info(f"Story arc deduplicator initialized (threshold: {self.similarity_threshold})")

    def run(self):
        """Run the deduplication process."""
        self.logger.info("Starting story arc deduplication...")

        with self.db_manager.get_session() as session:
            # Load all story arcs
            arcs = session.query(StoryArc).order_by(StoryArc.id).all()
            if len(arcs) < 2:
                self.logger.info(f"Only {len(arcs)} story arcs - nothing to deduplicate")
                return {'success': True, 'merged_groups': 0, 'arcs_merged': 0}

            self.logger.info(f"Loaded {len(arcs)} story arcs for deduplication")

            # Group arcs by digest_topic for efficiency
            by_topic = defaultdict(list)
            for arc in arcs:
                by_topic[arc.digest_topic].append(arc)

            total_merged = 0
            total_groups = 0

            for topic_name, topic_arcs in by_topic.items():
                if len(topic_arcs) < 2:
                    continue

                self.logger.info(f"\nProcessing topic '{topic_name}' ({len(topic_arcs)} arcs)")
                merged, groups = self._deduplicate_arcs(session, topic_arcs)
                total_merged += merged
                total_groups += groups

            if not self.dry_run:
                session.commit()
                self.logger.info(f"Changes committed to database")

        self.logger.info(f"\nDeduplication complete: {total_groups} groups found, {total_merged} arcs merged")
        return {
            'success': True,
            'merged_groups': total_groups,
            'arcs_merged': total_merged
        }

    def _deduplicate_arcs(self, session, arcs):
        """Find and merge duplicate arcs within a topic group using semantic matching."""
        from src.topic_tracking.semantic_matcher import SemanticTopicMatcher

        matcher = SemanticTopicMatcher(similarity_threshold=self.similarity_threshold)

        # Build text representations for each arc
        arc_texts = {}
        for arc in arcs:
            # Combine arc name + summary for embedding
            text = arc.arc_name
            if arc.summary:
                text += " " + arc.summary
            arc_texts[arc.id] = text

        # Find similar pairs using embeddings
        arc_ids = list(arc_texts.keys())
        texts = [arc_texts[aid] for aid in arc_ids]

        # Get embeddings for all arcs individually
        embeddings = []
        for text in texts:
            emb = matcher._get_embedding(text)
            embeddings.append(emb)

        if not embeddings or len(embeddings) != len(arc_ids):
            self.logger.warning("Failed to get embeddings for arcs")
            return 0, 0

        # Find groups of similar arcs using union-find
        import numpy as np
        parent = {aid: aid for aid in arc_ids}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        # Compare all pairs
        for i in range(len(arc_ids)):
            for j in range(i + 1, len(arc_ids)):
                sim = np.dot(embeddings[i], embeddings[j])
                if sim >= self.similarity_threshold:
                    union(arc_ids[i], arc_ids[j])
                    self.logger.debug(
                        f"  Similar ({sim:.3f}): #{arc_ids[i]} '{arc_texts[arc_ids[i]][:50]}' "
                        f"↔ #{arc_ids[j]} '{arc_texts[arc_ids[j]][:50]}'"
                    )

        # Build groups
        groups = defaultdict(list)
        for aid in arc_ids:
            groups[find(aid)].append(aid)

        # Filter to groups with 2+ members (actual duplicates)
        merge_groups = {root: members for root, members in groups.items() if len(members) > 1}

        if not merge_groups:
            self.logger.info("  No duplicate arcs found")
            return 0, 0

        merged_count = 0
        for root_id, member_ids in merge_groups.items():
            arc_map = {arc.id: arc for arc in arcs}
            group_arcs = [arc_map[mid] for mid in member_ids if mid in arc_map]

            if len(group_arcs) < 2:
                continue

            # Keep the arc with the most events as the primary
            group_arcs.sort(key=lambda a: a.event_count, reverse=True)
            primary = group_arcs[0]
            duplicates = group_arcs[1:]

            self.logger.info(
                f"  MERGE GROUP: Keep #{primary.id} '{primary.arc_name[:60]}' "
                f"(events={primary.event_count}), merge {len(duplicates)} duplicate(s)"
            )

            if self.dry_run:
                for dup in duplicates:
                    self.logger.info(f"    [DRY RUN] Would merge #{dup.id} '{dup.arc_name[:50]}' → #{primary.id}")
                merged_count += len(duplicates)
                continue

            # Merge: move events from duplicates to primary, then delete duplicates
            for dup in duplicates:
                # Move events
                events = session.query(StoryArcEvent).filter(
                    StoryArcEvent.story_arc_id == dup.id
                ).all()

                for event in events:
                    event.story_arc_id = primary.id

                # Update primary's counters
                primary.event_count += dup.event_count
                primary.source_count = max(primary.source_count, dup.source_count)
                if dup.started_at < primary.started_at:
                    primary.started_at = dup.started_at
                if dup.last_updated_at > primary.last_updated_at:
                    primary.last_updated_at = dup.last_updated_at

                self.logger.info(f"    Merged #{dup.id} '{dup.arc_name[:50]}' → #{primary.id}")

                # Delete the duplicate arc
                session.delete(dup)
                merged_count += 1

        return merged_count, len(merge_groups)


def main():
    parser = argparse.ArgumentParser(description='Story Arc Deduplication Phase')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be merged')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    parser.add_argument('--threshold', type=float, help='Similarity threshold (0.0-1.0)', default=None)
    parser.add_argument('--output-json', help='Output JSON file path')
    # Accepted from the orchestrator's shared phase-launcher (which passes --limit
    # to every phase). Currently not enforced inside the deduplicator — arc
    # dedup processes all eligible arcs — but we accept it so the phase doesn't
    # argparse-error and get silently skipped. See Apr 18 root-cause analysis.
    parser.add_argument('--limit', type=int, default=None,
                        help='(accepted from orchestrator; currently unused by arc dedup)')

    args = parser.parse_args()

    dry_run = resolve_dry_run_flag(args.dry_run)

    try:
        deduplicator = StoryArcDeduplicator(
            dry_run=dry_run,
            verbose=args.verbose,
            similarity_threshold=args.threshold
        )

        result = deduplicator.run()

        # Output JSON result
        from src.utils.phase_output import write_phase_result
        write_phase_result(result, args.output_json)

        sys.exit(0 if result['success'] else 1)

    except Exception as e:
        error_result = {
            'success': False,
            'error': str(e),
            'merged_groups': 0,
            'arcs_merged': 0
        }

        from src.utils.phase_output import write_phase_result
        write_phase_result(error_result, getattr(args, 'output_json', None))
        sys.exit(1)


if __name__ == '__main__':
    main()
