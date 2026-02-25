#!/usr/bin/env python3
"""
Test claude -p metadata generation with episode_links.

Pulls a recent digest from database, generates metadata via claude -p,
and prints the result including episode links for inspection.

Usage:
    python3 scripts/test_claude_p_metadata.py [--digest-id 549]
"""

import os
import sys
import argparse
import json
from pathlib import Path

# Ensure project root is on sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Load environment variables
env_path = Path(project_root) / '.env'
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            key, _, value = line.partition('=')
            os.environ[key.strip()] = value.strip()


def get_recent_digest(digest_id: int = None):
    """Pull a digest and its linked episodes from the database."""
    from src.database.models import get_database_manager
    from src.database.sqlalchemy_models import Digest
    from sqlalchemy import text

    db = get_database_manager()
    session = db.get_session()

    if digest_id:
        digest = session.query(Digest).filter(Digest.id == digest_id).first()
    else:
        # Get most recent digest with script_content
        digest = (
            session.query(Digest)
            .filter(Digest.script_content.isnot(None))
            .order_by(Digest.id.desc())
            .first()
        )

    if not digest:
        print(f"ERROR: No digest found (id={digest_id})")
        sys.exit(1)

    # Get linked episodes with feed names
    result = session.execute(
        text("""
            SELECT e.title, e.audio_url, f.title as feed_name
            FROM digest_episode_links del
            JOIN episodes e ON del.episode_id = e.id
            JOIN feeds f ON e.feed_id = f.id
            WHERE del.digest_id = :did
        """),
        {"did": digest.id}
    )
    rows = result.fetchall()
    episodes = [{"title": r[0], "audio_url": r[1] or '', "feed_name": r[2]} for r in rows]

    session.close()
    return digest, episodes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--digest-id', type=int, default=None,
                        help='Digest ID to use (default: most recent)')
    args = parser.parse_args()

    print("=" * 60)
    print("CLAUDE -P METADATA GENERATION TEST")
    print("=" * 60)

    # 1. Load digest
    print(f"\n1. Loading digest{f' {args.digest_id}' if args.digest_id else ' (most recent)'}...")
    digest, episodes = get_recent_digest(args.digest_id)
    print(f"   Digest ID: {digest.id}")
    print(f"   Topic:     {digest.topic}")
    print(f"   Date:      {digest.digest_date}")
    print(f"   Script:    {len(digest.script_content or ''):,} chars")
    print(f"   Episodes:  {len(episodes)}")
    for ep in episodes:
        print(f"     - [{ep['feed_name']}] {ep['title'][:60]}")
        if ep['audio_url']:
            print(f"       {ep['audio_url'][:80]}")

    # 2. Generate metadata via claude -p
    print(f"\n2. Generating metadata via claude -p...")
    from src.audio.metadata_generator import MetadataGenerator
    import time

    mg = MetadataGenerator()
    start = time.time()
    metadata = mg.generate_metadata_for_digest(digest, episodes=episodes)
    elapsed = time.time() - start

    print(f"   Generated in {elapsed:.1f}s")

    # 3. Display results
    print(f"\n{'='*60}")
    print(f"  METADATA RESULT")
    print(f"{'='*60}")
    print(f"  Title:    {metadata.title}")
    print(f"  Summary:  {metadata.summary}")
    print(f"  Keywords: {metadata.keywords}")
    print(f"  Category: {metadata.category}")
    print(f"\n  Episode Links ({len(metadata.episode_links or [])}):")
    for link in (metadata.episode_links or []):
        print(f"    Feed:  {link.get('feed_name', '?')}")
        print(f"    Title: {link.get('title', '?')}")
        print(f"    URL:   {link.get('audio_url', '?')[:80]}")
        print()

    # 4. Validation checks
    print(f"{'='*60}")
    print(f"  VALIDATION")
    print(f"{'='*60}")
    checks = [
        ("Title ≤ 70 chars", len(metadata.title) <= 70),
        ("Summary ≤ 250 chars", len(metadata.summary) <= 250),
        ("Has keywords", bool(metadata.keywords)),
        ("Has category", bool(metadata.category)),
        ("Has episode_links", bool(metadata.episode_links)),
        ("Episode links count matches", len(metadata.episode_links or []) == len(episodes)),
    ]
    all_pass = True
    for label, passed in checks:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  [{status}] {label}")

    print()
    if all_pass:
        print("  All checks passed.")
    else:
        print("  Some checks FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    main()
