#!/usr/bin/env python3
"""Replay a past digest's episode set through the CURRENT generation code.

Built to answer "would v4.01 have prevented the 2026-08-08 duplicate intro?"
and reusable for any before/after question about script generation.

READ-ONLY against production state. It calls generate_script() and
finalize_script() directly rather than create_digest(), so it never writes a
digests row, never marks an episode digested, never touches story arcs, and
never runs TTS. The only writes are the output files you ask for.

    # Replay the incident: same nine episodes, current code
    python3 scripts/replay_digest.py --digest-id 724

    # Same, but withhold the saturated-topic block to see the old behavior
    python3 scripts/replay_digest.py --digest-id 724 --no-repetition-block

    # Skip the ~6 min of pre-gen dedup when iterating on prompt wording
    python3 scripts/replay_digest.py --digest-id 724 --skip-dedup

Every run prints the lead-repeat score against the real prior digests, which
is the number the whole exercise is about.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text  # noqa: E402

from src.database.models import get_database_manager  # noqa: E402
from src.generation import lead_repeat_guard as guard  # noqa: E402
from src.generation.script_generator import ScriptGenerator  # noqa: E402

logger = logging.getLogger("replay")


def install_legacy_prompt(gen: ScriptGenerator) -> None:
    """Restore the exact pre-v4.01 dialogue prompt on this instance.

    Two things made the 2026-08-08 prompt what it was, and a faithful control
    needs both: the dynamic blocks were accepted and then dropped, and in
    their place sat an unconditional claim that everything in the transcripts
    was new. Removing only the block (--no-repetition-block) gives a neutral
    arm, not the old behavior, because the false assertion is gone from the
    source now.
    """
    from pathlib import Path as _Path

    def legacy(self, system_prompt, topic, topic_instructions, story_arc_context,
               repetition_instructions, digest_date, speaker_1_name, speaker_2_name,
               num_episodes, theme_emphasis=None):
        skill_path = (_Path(__file__).parent.parent / '.claude' / 'commands'
                      / 'generate-digest.md')
        if not skill_path.exists():
            return system_prompt  # legacy fallback dropped them too
        prompt = (
            f"{skill_path.read_text()}\n\n"
            f"## Topic-Specific Instructions\n{topic_instructions}\n\n"
            f"**PRE-FILTERED TRANSCRIPTS:** These transcripts have been pre-filtered "
            f"to remove content already covered in recent episodes. Everything provided "
            f"is NEW material. Cover it all thoroughly.\n\n"
            f"Date: {digest_date.strftime('%B %d, %Y')}\n"
            f"Topic: {topic}\n"
            f"Episodes: {num_episodes}\n\n"
            f"CHARACTER ROLES:\n"
            f"- SPEAKER_1 ({speaker_1_name}): Primary host, introduces topics, asks questions\n"
            f"- SPEAKER_2 ({speaker_2_name}): Expert analyst, provides insights and analysis"
        )
        if theme_emphasis:
            prompt += f"\n\n{theme_emphasis}"
        return prompt

    gen._build_claude_p_dialogue_prompt = legacy.__get__(gen, ScriptGenerator)


def load_digest_pool(digest_id: int):
    """Return (topic, digest_date, [Episode]) for a past digest, in order."""
    from src.database.models import EpisodeRepository

    db = get_database_manager()
    session = db.get_session()
    try:
        row = session.execute(
            text("select topic, digest_date from digests where id = :d"), {"d": digest_id}
        ).fetchone()
        if not row:
            raise SystemExit(f"No digest {digest_id}")
        topic, digest_date = row[0], row[1]

        ep_ids = [
            r[0]
            for r in session.execute(
                text(
                    "select episode_id from digest_episode_links "
                    "where digest_id = :d order by position"
                ),
                {"d": digest_id},
            ).fetchall()
        ]
    finally:
        session.close()

    repo = EpisodeRepository(db)
    episodes = []
    for eid in ep_ids:
        ep = repo.get_by_id(eid)
        if ep is None:
            logger.warning(f"episode {eid} no longer present, skipping")
        elif not (ep.transcript_content or "").strip():
            logger.warning(f"episode {eid} has no transcript, skipping")
        else:
            episodes.append(ep)
    return topic, digest_date, episodes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--digest-id", type=int, required=True)
    ap.add_argument("--skip-dedup", action="store_true",
                    help="skip pre-gen transcript dedup (~6 min) -- prompt-only iteration")
    ap.add_argument("--no-repetition-block", action="store_true",
                    help="withhold the saturated-topic block (neutral arm: neither the "
                         "v4.01 constraint nor the old false assertion)")
    ap.add_argument("--legacy-prompt", action="store_true",
                    help="faithfully reproduce the pre-v4.01 prompt: discard the dynamic "
                         "blocks AND restore the 'Everything provided is NEW material' "
                         "assertion. This is the real control arm.")
    ap.add_argument("--trials", type=int, default=1,
                    help="repeat N times; generation is stochastic, so one run proves little")
    ap.add_argument("--no-provenance", action="store_true",
                    help="disable the v4.01 dedup provenance check, so dedup can once again "
                         "emit text absent from its input. Pair with --legacy-prompt to "
                         "reproduce the pre-v4.01 pipeline end to end.")
    ap.add_argument("--out", type=str, default=None, help="write the script here")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    for noisy in ("httpx", "httpcore", "openai", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    topic, digest_date, episodes = load_digest_pool(args.digest_id)
    print(f"\nReplaying digest {args.digest_id}: {topic} / {digest_date} / {len(episodes)} episodes")
    for ep in episodes:
        print(f"   {ep.id:>5}  {len(ep.transcript_content or ''):>7,} chars  {ep.title[:60]}")

    gen = ScriptGenerator()

    # Saturated topics, the same way create_digest derives them.
    has_overlap, msg, saturated = gen._check_topic_repetition(episodes, topic)
    print(f"\nsaturated-topic check: overlap={has_overlap} ({msg})")
    for name in saturated or []:
        print(f"   - {name}")
    if args.no_repetition_block:
        saturated = None
        print("   (withheld via --no-repetition-block)")

    # Pre-generation dedup, unless skipped. Mirrors create_digest but keeps
    # everything in memory.
    if not args.skip_dedup:
        from src.generation import transcript_dedup as _td
        from src.generation.transcript_dedup import dedup_episode_batch

        if args.no_provenance:
            _td._invented_sentences = lambda *a, **k: []
            print("\n*** PROVENANCE CHECK DISABLED: dedup may emit text absent "
                  "from its input, as it could before v4.01 ***")

        db = get_database_manager()
        session = db.get_session()
        try:
            prior_scripts = [
                r[0]
                for r in session.execute(
                    text(
                        "select script_content from digests where topic = :t "
                        "and script_content is not null and id < :d "
                        "order by generated_at desc limit 14"
                    ),
                    {"t": topic, "d": args.digest_id},
                ).fetchall()
            ]
        finally:
            session.close()

        print(f"\npre-gen dedup against {len(prior_scripts)} prior digests...")
        results, _ = dedup_episode_batch(episodes, prior_digest_scripts=prior_scripts)
        kept = []
        for ep, res in zip(episodes, results):
            if res.below_floor_action == "dropped":
                print(f"   DROPPED {ep.id}: {ep.title[:55]}")
                continue
            if not res.skipped and res.deduped_transcript:
                ep.transcript_content = res.deduped_transcript
            kept.append(ep)
        episodes = kept
        print(f"   {len(episodes)} episodes survive dedup")

    if args.legacy_prompt:
        install_legacy_prompt(gen)
        saturated = None
        print("\n*** LEGACY PROMPT ARM: dynamic blocks discarded, "
              "'everything is NEW material' assertion restored ***")

    scores = []
    for trial in range(1, args.trials + 1):
        if args.trials > 1:
            print(f"\n--- trial {trial}/{args.trials} ---")
        scores.append(run_one(gen, topic, episodes, digest_date, saturated, args, trial))

    if args.trials > 1:
        print("\n" + "=" * 72)
        print(f"{args.trials} trials: scores {[round(s, 3) for s in scores]}")
        print(f"max {max(scores):.3f}   tripped "
              f"{sum(1 for s in scores if s >= guard.DEFAULT_THRESHOLD)}/{args.trials}")
        print("=" * 72)
    return 0


def run_one(gen, topic, episodes, digest_date, saturated, args, trial: int) -> float:
    print("generating...")
    script, _ = gen.generate_script(topic, episodes, digest_date, recently_covered_arcs=saturated)

    # already_varied=True: generate_script has just run the variety pass on
    # this exact text. Production passes False only when the expansion loop
    # regenerated the draft afterwards, discarding that work. Passing False
    # here would double-apply the pass to the same text and make the replay
    # less faithful than the thing it is replaying.
    script = gen.finalize_script(
        script, topic=topic, dialogue=gen._is_dialogue_mode(topic), already_varied=True
    )

    # The number this exercise exists to produce: how close is the lead to
    # what actually shipped in the days before this digest?
    db = get_database_manager()
    session = db.get_session()
    try:
        priors = [
            {"id": r[0], "date": str(r[1]), "content": r[2]}
            for r in session.execute(
                text(
                    "select id, digest_date, script_content from digests where topic = :t "
                    "and script_content is not null and id < :d "
                    "order by generated_at desc limit 3"
                ),
                {"t": topic, "d": args.digest_id},
            ).fetchall()
        ]
    finally:
        session.close()

    result = guard.check_lead_repeat(script, topic=topic, prior_digests=priors)

    print("\n" + "=" * 72)
    print(f"chars: {len(script):,}")
    print(f"lead-repeat vs digest {result.matched_digest_id} ({result.matched_digest_date}): "
          f"{result.score:.3f}  threshold {result.threshold}  tripped={result.tripped}")
    print(f"windows: {result.scores_by_window}")
    print("=" * 72)
    print("\nLEAD:\n")
    print(guard.extract_lead(script))

    # Did it lead with the story the previous digest led with? The score is
    # the formal answer; this is the human-readable one.
    lead_l = guard.extract_lead(script).lower()
    print("leads with DeepMind/Hassabis/Jeff Dean: "
          f"{any(k in lead_l for k in ('hassabis', 'jeff dean', 'deepmind'))}")

    if args.out:
        out = Path(args.out)
        if args.trials > 1:
            out = out.with_name(f"{out.stem}_t{trial}{out.suffix}")
        out.write_text(script)
        print(f"wrote {out}")
    return result.score


if __name__ == "__main__":
    sys.exit(main())
