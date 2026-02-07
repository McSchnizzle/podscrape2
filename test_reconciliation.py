#!/usr/bin/env python3
"""
Test script for DigestArcReconciler.

Queries real digest scripts from the database and runs reconciliation
in dry-run mode to verify detection of recurring stories.

Uses real OpenAI API calls - requires OPENAI_API_KEY.
"""

import sys
from pathlib import Path

# Bootstrap
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))
from src.utils.phase_bootstrap import bootstrap_phase
bootstrap_phase()

import logging
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_reconciliation():
    """Test reconciliation in dry-run mode against real digest data."""
    from src.topic_tracking.digest_arc_reconciler import DigestArcReconciler

    logger.info("=" * 60)
    logger.info("DigestArcReconciler Test (Dry Run)")
    logger.info("=" * 60)

    reconciler = DigestArcReconciler()

    # Test with AI and Technology topic
    topic = "AI and Technology"
    logger.info(f"\nTesting reconciliation for topic: '{topic}'")

    # Check how many recent digests exist
    scripts = reconciler._get_recent_digest_scripts(topic)
    logger.info(f"Found {len(scripts)} recent digest scripts")

    if not scripts:
        logger.warning("No digest scripts found - test cannot proceed")
        logger.info("This is expected if no digests have been generated for this topic recently.")
        return

    for s in scripts:
        content_preview = s['content'][:100].replace('\n', ' ')
        logger.info(f"  [{s['date']}] {content_preview}...")

    # Run reconciliation in dry-run mode
    logger.info(f"\nRunning reconciliation (dry_run=True)...")
    result = reconciler.reconcile(topic, dry_run=True)

    logger.info(f"\n{'=' * 60}")
    logger.info(f"RESULTS:")
    logger.info(f"  Stories found: {result['stories_found']}")
    logger.info(f"  Arcs that would be created: {result['arcs_created']}")
    logger.info(f"  Arcs skipped (already exist): {result['arcs_skipped']}")
    logger.info(f"  Message: {result['message']}")

    if result['details']:
        logger.info(f"\nDETAILS:")
        for detail in result['details']:
            story = detail.get('story', 'unknown')
            action = detail.get('action', 'unknown')
            occurrences = detail.get('occurrences', '?')
            if action == 'would_create':
                logger.info(f"  + WOULD CREATE: '{story}' ({occurrences} occurrences)")
                logger.info(f"    Category: {detail.get('category', '?')}")
                logger.info(f"    Summary: {detail.get('summary', '?')}")
            elif action == 'skipped':
                logger.info(f"  - SKIPPED: '{story}' ({occurrences} occurrences)")
                logger.info(f"    Reason: {detail.get('reason', '?')}")

    logger.info(f"\n{'=' * 60}")
    logger.info("Test complete.")

    return result


if __name__ == '__main__':
    result = test_reconciliation()
    sys.exit(0)
