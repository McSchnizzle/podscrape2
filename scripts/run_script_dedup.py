#!/usr/bin/env python3
"""
Script-level dedup CLI — run the post-generation dedup pass against an
existing digest for tuning, inspection, or reprocessing.

Not to be confused with scripts/run_dedup.py, which is the story-arc dedup.

Usage:
    python3 scripts/run_script_dedup.py --digest-id 597 --dry-run
    python3 scripts/run_script_dedup.py --digest-id 597 --apply
    python3 scripts/run_script_dedup.py --digest-id 597 --lookback 14 --dry-run
"""
import argparse
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from src.utils.phase_bootstrap import bootstrap_phase
bootstrap_phase()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the post-gen dedup pass on an existing digest")
    parser.add_argument("--digest-id", type=int, required=True, help="Digest ID to operate on")
    parser.add_argument("--lookback", type=int, default=8, help="Number of prior digests to compare against")
    parser.add_argument("--dry-run", action="store_true", help="Print diff without writing")
    parser.add_argument("--apply", action="store_true", help="Write the deduped script back to the database")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        print("ERROR: must specify --dry-run or --apply", file=sys.stderr)
        return 2

    from src.database.models import get_database_manager
    from src.database.sqlalchemy_models import Digest as DigestModel
    from src.generation.dedup_pass import run_dedup_pass

    db = get_database_manager()
    with db.get_session() as session:
        digest = session.query(DigestModel).filter(DigestModel.id == args.digest_id).first()
        if not digest:
            print(f"ERROR: no digest found with id={args.digest_id}", file=sys.stderr)
            return 1

        print(f"Digest {digest.id}: topic='{digest.topic}' date={digest.digest_date}")
        print(f"  chars: {len(digest.script_content or '')}")
        print(f"  running dedup pass (lookback={args.lookback}, exclude_digest_id={digest.id})")

        result = run_dedup_pass(
            draft_script=digest.script_content or "",
            topic=digest.topic,
            lookback=args.lookback,
            exclude_digest_id=digest.id,
        )

        print()
        print("Result:")
        print(f"  before: {result.chars_before} chars")
        print(f"  after:  {result.chars_after} chars")
        print(f"  delta:  {result.delta:+d}")
        print(f"  lookback: {result.lookback_count} prior digests")
        print(f"  skipped: {result.skipped} ({result.skip_reason or '—'})")

        if result.skipped:
            return 0

        # Simple unified diff preview
        import difflib
        diff = difflib.unified_diff(
            (digest.script_content or "").splitlines(keepends=True),
            result.rewritten_script.splitlines(keepends=True),
            fromfile=f"digest-{digest.id}.predupe",
            tofile=f"digest-{digest.id}.deduped",
            lineterm="",
            n=2,
        )
        print()
        print("=== DIFF (first 200 lines) ===")
        for i, line in enumerate(diff):
            if i >= 200:
                print("... (diff truncated)")
                break
            print(line.rstrip())

        if args.apply:
            print()
            print(f"Applying dedup to digest {digest.id}...")
            if digest.script_content_predupe is None:
                digest.script_content_predupe = digest.script_content
            digest.script_content = result.rewritten_script
            digest.script_word_count = len(result.rewritten_script.split())
            session.commit()
            print(f"✓ Digest {digest.id} updated ({result.chars_before} -> {result.chars_after} chars)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
