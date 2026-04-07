#!/usr/bin/env python3
"""
End-to-end test of the new dedup + story arc structure.

Takes the episodes that were included in an existing digest, regenerates the
script from scratch using the new ScriptGenerator (which now includes the
SATURATED-arc prompt directive + the post-gen dedup pass), and reports the
result without touching TTS, without writing to the database.

Usage:
    python3 scripts/test_dedup_full_flow.py --digest-id 597
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--digest-id", type=int, required=True)
    args = parser.parse_args()

    from src.database.models import get_database_manager, get_episode_repo
    from src.database.sqlalchemy_models import Digest as DigestModel
    from src.generation.script_generator import ScriptGenerator
    from src.generation.dedup_pass import run_dedup_pass
    from src.config.web_config import WebConfigManager
    from sqlalchemy import text

    db = get_database_manager()
    with db.get_session() as session:
        digest = session.query(DigestModel).filter(DigestModel.id == args.digest_id).first()
        if not digest:
            print(f"ERROR: digest {args.digest_id} not found", file=sys.stderr)
            return 1
        topic = digest.topic
        digest_date = digest.digest_date
        rows = session.execute(
            text("SELECT episode_id FROM digest_episode_links WHERE digest_id=:id ORDER BY position"),
            {"id": args.digest_id},
        )
        episode_ids = [r[0] for r in rows]

    print(f"Test subject: digest {args.digest_id} '{topic}' ({digest_date})")
    print(f"  episodes: {episode_ids}")

    # Load Episode objects
    episode_repo = get_episode_repo()
    episodes = []
    for eid in episode_ids:
        ep = episode_repo.get_by_id(eid)
        if ep:
            episodes.append(ep)
    print(f"  loaded {len(episodes)} episode objects")
    for ep in episodes:
        print(f"    - id={ep.id} feed={ep.feed_id} '{ep.title[:60]}' "
              f"transcript={len(ep.transcript_content or '')} chars")

    # Initialize script generator
    try:
        web_config = WebConfigManager()
    except Exception:
        web_config = None

    try:
        from src.config.config_manager import ConfigManager
        sg = ScriptGenerator(
            web_config=web_config,
            config_manager=ConfigManager(web_config=web_config),
        )
    except Exception:
        sg = ScriptGenerator(web_config=web_config)

    # Check story arc repetition (the same check create_digest runs)
    print()
    print("=== Story arc repetition check ===")
    has_overlap, overlap_msg, recently_covered = sg._check_topic_repetition(episodes, topic)
    print(f"  has_overlap: {has_overlap}")
    print(f"  msg: {overlap_msg}")
    print(f"  recently_covered_arcs: {recently_covered[:5]}")

    # Generate the draft (this is what create_digest calls)
    print()
    print("=== Generating fresh draft script ===")
    draft, word_count = sg.generate_script(
        topic,
        episodes,
        digest_date,
        recently_covered_arcs=recently_covered if has_overlap else None,
    )
    print(f"  draft chars: {len(draft)}")
    print(f"  draft words: {word_count}")

    # Run the dedup pass with retry (same as production)
    print()
    print("=== Running dedup pass (with potential retry) ===")
    result = sg._run_dedup_pass_with_retry(
        topic=topic,
        draft_script=draft,
        episodes=episodes,
        digest_date=digest_date,
        recently_covered_arcs=recently_covered if has_overlap else None,
    )
    if result is None:
        print("  dedup pass not run (disabled or skipped)")
        return 0

    final_script = result["script_content"]
    final_episodes = result["episodes"]
    predupe = result["predupe_content"]

    print(f"  final script: {len(final_script)} chars / {result['word_count']} words")
    print(f"  predupe:      {len(predupe)} chars")
    print(f"  delta:        {len(final_script) - len(predupe):+d}")
    print(f"  episodes used: {len(final_episodes)} (started with {len(episodes)})")

    # Dump the final script to a temp file for inspection
    out_path = project_root / f".test_dedup_digest_{args.digest_id}.md"
    out_path.write_text(final_script, encoding="utf-8")
    predupe_path = project_root / f".test_dedup_digest_{args.digest_id}.predupe.md"
    predupe_path.write_text(predupe, encoding="utf-8")
    print()
    print(f"  wrote final  -> {out_path}")
    print(f"  wrote predupe -> {predupe_path}")

    # Show a short preview of the final
    print()
    print("=== Final script preview (first 800 chars) ===")
    print(final_script[:800])
    print("...")

    return 0


if __name__ == "__main__":
    sys.exit(main())
