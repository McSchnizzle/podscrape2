#!/usr/bin/env python3
"""Versioned update: AI and Technology instructions_md v5 -- engineering-depth ceiling.

kanban #2855 Tier 1 reciprocal. Paul's example: a recent "risk manager/
assessor agent" discussion went too deep into implementation minutiae for
the show. This script appends a rule to the "AI and Technology" topic's
instructions_md steering the digest away from framework internals,
agent-implementation walkthroughs, and code-level detail unless there is a
strong listener-facing story -- that depth belongs in the R&D pipeline
(scripts/rnd_miner.py), not the episode script.

This is a SCRIPT, not a migration that runs automatically. It does NOT
touch the live database by default -- it only writes topic_instruction_versions
v5 (and the data/instructions_md_backup_<date>.md snapshot) when invoked
with --apply. Paul reviews the diff first.

Usage:
    # Preview the new instructions_md (no DB write, no file write):
    python3 scripts/apply_ai_tech_instructions_v5_engineering_depth.py

    # Apply: writes topic_instruction_versions v5 + data/instructions_md_backup_<date>.md
    python3 scripts/apply_ai_tech_instructions_v5_engineering_depth.py --apply
"""

import argparse
import sys
from datetime import date
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

TOPIC_NAME = "AI and Technology"
CHANGE_NOTE = (
    "v5: add engineering-depth ceiling -- implementation-level minutiae "
    "(framework internals, agent-implementation details, code-level "
    "walkthroughs) get at most a brief mention on air unless there is a "
    "strong listener-facing story; deep coverage belongs to the R&D "
    "pipeline (kanban #2855), not the episode. Prompted by an "
    "over-technical 'risk manager/assessor agent' segment."
)

# The new section is inserted right after "## Conditional Emphasis:
# Standards, Governance, and Consortiums" -- same family of "when this kind
# of material shows up, here's how much air time it gets" guidance, kept
# together so a script writer reads both conditional-emphasis rules in one
# place.
NEW_SECTION_ANCHOR = "## Conditional Emphasis: Standards, Governance, and Consortiums"

NEW_SECTION = """
## Engineering-Depth Ceiling
- Implementation-level engineering minutiae -- framework internals, agent-implementation architecture, code-level walkthroughs, API/parameter-by-parameter tours -- gets at most a brief mention on air, not a full segment, unless there is a strong listener-facing story wrapped around it (a product launch, a real-world failure, a decision that affects how people use these tools day to day).
- That depth is exactly what the R&D pipeline is for: episodes with strong engineering-depth content still feed Harold's own R&D mining, just not at that depth on the show.
- Rule of thumb: if the segment would only land with someone who has actually built an agent system, trim it to the listener-facing takeaway and move on."""


def build_v5_instructions(current_instructions_md: str) -> str:
    """Insert NEW_SECTION right before NEW_SECTION_ANCHOR.

    Falls back to appending at the end if the anchor text isn't found
    (defensive -- instructions_md is hand-edited and the anchor heading
    could change wording in a future version).
    """
    if NEW_SECTION_ANCHOR in current_instructions_md:
        return current_instructions_md.replace(
            NEW_SECTION_ANCHOR,
            NEW_SECTION.strip("\n") + "\n\n" + NEW_SECTION_ANCHOR,
            1,
        )
    return current_instructions_md.rstrip("\n") + "\n\n" + NEW_SECTION.strip("\n") + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                         help="Write topic_instruction_versions v5 to the live DB and a "
                              "data/instructions_md_backup_<date>.md snapshot. "
                              "Without this flag, only prints the proposed instructions_md.")
    parser.add_argument("--created-by", default="rnd-miner-2855-script",
                         help="created_by value recorded on the new instruction version.")
    args = parser.parse_args(argv)

    from src.database.models import get_topic_repo

    topic_repo = get_topic_repo()
    topics = topic_repo.get_all_topics()
    topic = next((t for t in topics if t.name == TOPIC_NAME), None)
    if topic is None:
        print(f"ERROR: topic '{TOPIC_NAME}' not found in DB", file=sys.stderr)
        return 1

    current_md = topic.instructions_md or ""
    new_md = build_v5_instructions(current_md)

    if new_md == current_md:
        print(f"No change: NEW_SECTION already present or anchor text missing for '{TOPIC_NAME}'.")
        return 0

    if not args.apply:
        print("=== DRY RUN (pass --apply to write) ===\n")
        print(new_md)
        return 0

    version = topic_repo.update_instructions(
        topic.id, new_md, change_note=CHANGE_NOTE, created_by=args.created_by
    )
    print(f"Applied: topic_instruction_versions v{version.version} for '{TOPIC_NAME}'")

    backup_path = project_root / "data" / f"instructions_md_backup_{date.today():%Y%m%d}.md"
    backup_path.write_text(new_md)
    print(f"Wrote backup: {backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
