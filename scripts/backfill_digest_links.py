#!/usr/bin/env python3
"""
Backfill digest_episode_links from episode_ids JSON column.

GitHub Issue #10: Unify digest-episode linkage (single source of truth)

This script ensures all digests with episode_ids have corresponding entries
in the digest_episode_links join table. This is part of the migration to
use digest_episode_links as the single source of truth.

Usage:
    python3 scripts/backfill_digest_links.py --dry-run  # Show what would be done
    python3 scripts/backfill_digest_links.py            # Actually perform backfill
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from src.config.env import load_env
load_env()

from src.database.models import (
    get_database_manager,
    DigestEpisodeLink,
    get_digest_episode_link_repo,
)
from src.database.sqlalchemy_models import (
    Digest as DigestModel,
    DigestEpisodeLink as DigestEpisodeLinkModel,
    Episode as EpisodeModel,
)
from sqlalchemy import text


def backfill_digest_links(dry_run: bool = True):
    """
    Backfill digest_episode_links from episode_ids JSON column.

    Args:
        dry_run: If True, only show what would be done without making changes.
    """
    db_manager = get_database_manager()
    link_repo = get_digest_episode_link_repo()

    print("=" * 60)
    print("Backfill Digest Episode Links")
    print("=" * 60)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE - CHANGES WILL BE MADE'}")
    print()

    with db_manager.get_session() as session:
        # Find digests with episode_ids but no corresponding links
        result = session.execute(text('''
            SELECT d.id, d.topic, d.digest_date, d.episode_ids
            FROM digests d
            WHERE d.episode_ids IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM digest_episode_links del WHERE del.digest_id = d.id
              )
            ORDER BY d.digest_date DESC
        '''))

        digests_to_backfill = result.fetchall()

        if not digests_to_backfill:
            print("No digests need backfilling - all episode_ids have corresponding links.")
            return

        print(f"Found {len(digests_to_backfill)} digests needing backfill:")
        print("-" * 60)

        total_links_created = 0
        errors = []

        for digest_row in digests_to_backfill:
            digest_id = digest_row.id
            topic = digest_row.topic
            digest_date = digest_row.digest_date
            episode_ids = digest_row.episode_ids  # This is a list from JSONB

            if not episode_ids:
                print(f"  Digest {digest_id} ({topic}, {digest_date}): No episode_ids, skipping")
                continue

            # Validate episode IDs exist
            valid_episode_ids = []
            for ep_id in episode_ids:
                episode = session.query(EpisodeModel).filter(EpisodeModel.id == ep_id).first()
                if episode:
                    valid_episode_ids.append(ep_id)
                else:
                    print(f"    Warning: Episode {ep_id} not found in database")

            if not valid_episode_ids:
                print(f"  Digest {digest_id} ({topic}, {digest_date}): No valid episodes found, skipping")
                continue

            print(f"  Digest {digest_id} ({topic}, {digest_date}): {len(valid_episode_ids)} episodes")

            if dry_run:
                for position, ep_id in enumerate(valid_episode_ids, start=1):
                    print(f"    [DRY RUN] Would create link: digest={digest_id}, episode={ep_id}, position={position}")
                total_links_created += len(valid_episode_ids)
            else:
                # Create links using repository
                links = []
                for position, ep_id in enumerate(valid_episode_ids, start=1):
                    # Try to get score from episode's scores if available
                    episode = session.query(EpisodeModel).filter(EpisodeModel.id == ep_id).first()
                    score = None
                    if episode and episode.scores and topic in episode.scores:
                        score = episode.scores[topic]

                    links.append(DigestEpisodeLink(
                        digest_id=digest_id,
                        episode_id=ep_id,
                        topic=topic,
                        score=score,
                        position=position,
                        created_at=datetime.now(timezone.utc)
                    ))

                try:
                    link_repo.replace_links_for_digest(digest_id, links)
                    print(f"    Created {len(links)} links for digest {digest_id}")
                    total_links_created += len(links)
                except Exception as e:
                    error_msg = f"Failed to create links for digest {digest_id}: {e}"
                    print(f"    ERROR: {error_msg}")
                    errors.append(error_msg)

        print()
        print("=" * 60)
        print("Summary")
        print("=" * 60)
        print(f"Digests processed: {len(digests_to_backfill)}")
        print(f"Links {'would be ' if dry_run else ''}created: {total_links_created}")
        if errors:
            print(f"Errors: {len(errors)}")
            for err in errors:
                print(f"  - {err}")

        if dry_run:
            print()
            print("This was a dry run. Run without --dry-run to actually create links.")


def verify_consistency():
    """Verify data consistency after backfill."""
    print()
    print("=" * 60)
    print("Verification")
    print("=" * 60)

    db_manager = get_database_manager()

    with db_manager.get_session() as session:
        # Check for mismatches
        result = session.execute(text('''
            SELECT d.id,
                   (d.episode_ids IS NOT NULL) as has_json,
                   EXISTS(SELECT 1 FROM digest_episode_links del WHERE del.digest_id = d.id) as has_links
            FROM digests d
            WHERE (d.episode_ids IS NOT NULL) != EXISTS(SELECT 1 FROM digest_episode_links del WHERE del.digest_id = d.id)
        '''))
        mismatches = result.fetchall()

        if mismatches:
            print(f"WARNING: Still have {len(mismatches)} mismatched digests:")
            for m in mismatches[:10]:
                print(f"  Digest {m.id}: has_json={m.has_json}, has_links={m.has_links}")
        else:
            print("SUCCESS: All digests with episode_ids have corresponding links!")

        # Count totals
        digests_with_ids = session.execute(text(
            "SELECT COUNT(*) FROM digests WHERE episode_ids IS NOT NULL"
        )).scalar()
        digests_with_links = session.execute(text(
            "SELECT COUNT(DISTINCT digest_id) FROM digest_episode_links"
        )).scalar()

        print()
        print(f"Digests with episode_ids: {digests_with_ids}")
        print(f"Digests in digest_episode_links: {digests_with_links}")


def main():
    parser = argparse.ArgumentParser(description='Backfill digest_episode_links from episode_ids JSON')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be done without making changes')
    parser.add_argument('--verify-only', action='store_true',
                        help='Only run verification, no backfill')
    args = parser.parse_args()

    if args.verify_only:
        verify_consistency()
    else:
        backfill_digest_links(dry_run=args.dry_run)
        verify_consistency()


if __name__ == "__main__":
    main()
