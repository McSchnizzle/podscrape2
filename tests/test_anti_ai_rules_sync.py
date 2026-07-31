#!/usr/bin/env python3
"""The four copies of the anti-AI rules must not drift apart again.

They already did. Before 2026-07-31 the list lived in four places with 20 / 6 /
10 / 6 rules respectively, so a rule added in one spot was enforced in one pass
and silently ignored by the others. `doing a lot of work` was banned in two of
the four; the dedup pass had no contrasted-negation rule at all.

src/generation/anti_ai_rules.py is now the source of truth for the Python
prompts. The markdown skill file cannot import Python, so it stays a
hand-maintained copy -- these tests are what stop that copy from drifting.
"""
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.generation.anti_ai_rules import (  # noqa: E402
    CONTRASTED_NEGATION_RULE,
    all_banned_substrings,
    compact_banned_list,
    full_rules_block,
)

SKILL = REPO / ".claude" / "commands" / "generate-digest.md"
GENERATOR = REPO / "src" / "generation" / "script_generator.py"
DEDUP = REPO / "src" / "generation" / "dedup_pass.py"


@pytest.mark.parametrize("fragment", all_banned_substrings())
def test_skill_file_covers_every_rule(fragment):
    """Every phrase the module bans must appear in the markdown skill file."""
    text = SKILL.read_text(encoding="utf-8").lower()
    assert fragment.lower() in text, (
        f"'{fragment}' is banned in anti_ai_rules.py but missing from "
        f"{SKILL.name}, so the claude -p generation path will not enforce it"
    )


def test_contrasted_negation_covers_the_variants_not_just_one():
    """The original rule named only 'not just X, it's Y' and the model routed
    around it via synonyms: that exact form scored 0 hits in 14 days while the
    family scored 31. A rule naming one surface form teaches avoidance of that
    form, not of the habit."""
    for variant in ("not just", "isn't x", "that's not x"):
        assert variant in CONTRASTED_NEGATION_RULE.lower(), (
            f"contrasted-negation rule no longer names the '{variant}' variant"
        )


@pytest.mark.parametrize("path", [GENERATOR, DEDUP])
def test_every_prompt_pass_bans_contrasted_negation(path):
    """All three enforcement passes must carry it. dedup_pass had no rule at
    all, which is how the pattern survived the pass that rewrites drafts."""
    text = path.read_text(encoding="utf-8").lower()
    assert "contrasted negation" in text, (
        f"{path.name} has no contrasted-negation rule; the pattern will survive "
        f"this pass"
    )


def test_generator_uses_the_shared_list_not_a_private_copy():
    """The inline generation prompt used to hardcode 6 phrases. If someone
    re-inlines a list here, this catches it."""
    text = GENERATOR.read_text(encoding="utf-8")
    assert "from src.generation.anti_ai_rules import" in text
    assert "_ANTI_AI_COMPACT" in text


def test_compact_list_still_carries_contrasted_negation():
    """The short form is used where the full block will not fit. Contrasted
    negation was absent from EVERY short copy, which is exactly why it
    survived -- so it must never be dropped for brevity again."""
    compact = compact_banned_list().lower()
    assert "contrasted negation" in compact
    assert "isn't x" in compact


def test_full_block_renders_all_sections():
    block = full_rules_block()
    assert "Banned words and phrases" in block
    assert "Structural rules" in block
    assert "Contrasted negation" in block
    assert block.count("\n") > 15


def test_no_stale_gpt4o_model_guidance_in_live_docs():
    """Live guidance must not tell anyone to select a GPT-4o model.

    Scoped to the `gpt-4o` families, NOT to bare "gpt-4". Two legitimate uses of
    the bare string survive on purpose: `known_entities` in script_generator.py
    needs it to detect transcripts discussing GPT-4, and CLAUDE.md explains why
    that entry stays. Historical records (VERSION_GUIDE, phase notes,
    .agents/outputs) keep their mentions too -- rewriting history would be a lie.
    """
    for name in ("CLAUDE.md", "README.md"):
        f = REPO / name
        if not f.exists():
            continue
        hits = re.findall(r"gpt-4o[a-z0-9.-]*", f.read_text(encoding="utf-8"), re.I)
        assert not hits, f"{name} still recommends {set(hits)}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
