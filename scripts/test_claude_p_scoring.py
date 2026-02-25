#!/usr/bin/env python3
"""
Test claude -p topic scoring against the OpenAI baseline.

Pulls recent scored episodes from the database, re-scores them via claude -p,
and compares the results to the stored (OpenAI) scores.

Usage:
    python3 scripts/test_claude_p_scoring.py [--limit 3]
"""

import os
import sys
import argparse
import time
from pathlib import Path

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

env_path = Path(project_root) / '.env'
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            key, _, value = line.partition('=')
            os.environ[key.strip()] = value.strip()


def get_recent_scored_episodes(limit: int = 3):
    """Fetch recent episodes that have been scored and have transcripts."""
    from src.database.models import get_database_manager
    from sqlalchemy import text

    db = get_database_manager()
    session = db.get_session()
    result = session.execute(
        text("""
            SELECT id, title, transcript_content, scores
            FROM episodes
            WHERE status IN ('scored', 'digested')
              AND transcript_content IS NOT NULL
              AND scores IS NOT NULL
            ORDER BY id DESC
            LIMIT :lim
        """),
        {"lim": limit}
    )
    rows = result.fetchall()
    session.close()
    return [{"id": r[0], "title": r[1], "transcript": r[2], "stored_scores": r[3]} for r in rows]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=3,
                        help='Number of episodes to test (default: 3)')
    args = parser.parse_args()

    print("=" * 60)
    print("CLAUDE -P TOPIC SCORING TEST")
    print("=" * 60)

    print(f"\n1. Loading {args.limit} recent scored episodes...")
    episodes = get_recent_scored_episodes(args.limit)
    if not episodes:
        print("   ERROR: No scored episodes found")
        sys.exit(1)

    from src.scoring.content_scorer import ContentScorer
    scorer = ContentScorer()
    topics = scorer.topics
    print(f"   Topics: {[t['name'] for t in topics]}")

    print(f"\n2. Re-scoring {len(episodes)} episodes via claude -p...\n")

    all_pass = True
    for ep in episodes:
        title_short = ep['title'][:55] if ep['title'] else 'Unknown'
        transcript_len = len(ep['transcript'] or '')
        stored = ep['stored_scores'] or {}

        print(f"  Episode {ep['id']}: {title_short}")
        print(f"    Transcript: {transcript_len:,} chars")
        print(f"    Stored scores: {', '.join(f'{k}={v:.2f}' for k, v in stored.items())}")

        start = time.time()
        result = scorer.score_transcript(ep['transcript'], str(ep['id']))
        elapsed = time.time() - start

        if result.success:
            print(f"    Claude -p scores ({elapsed:.1f}s): "
                  f"{', '.join(f'{k}={v:.2f}' for k, v in result.scores.items())}")

            # Compare qualifying status (above/below 0.65 threshold)
            threshold = scorer.score_threshold
            for topic in topics:
                name = topic['name']
                stored_score = stored.get(name, 0.0)
                new_score = result.scores.get(name, 0.0)
                stored_qualifies = stored_score >= threshold
                new_qualifies = new_score >= threshold
                agree = stored_qualifies == new_qualifies
                delta = new_score - stored_score
                flag = "" if agree else " *** DISAGREE ***"
                print(f"    [{name}] stored={stored_score:.2f} → claude={new_score:.2f} "
                      f"(Δ{delta:+.2f}) qualify:{stored_qualifies}→{new_qualifies}{flag}")
                if not agree:
                    all_pass = False
        else:
            print(f"    FAILED: {result.error_message}")
            all_pass = False
        print()

    print("=" * 60)
    if all_pass:
        print("  All episodes scored — qualify/exclude decisions agree with stored scores.")
    else:
        print("  WARNING: Some qualify decisions differ from stored OpenAI scores.")
        print("  Review the *** DISAGREE *** entries above before deploying.")
    print("=" * 60)


if __name__ == "__main__":
    main()
