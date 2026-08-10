"""Tests for the v4.01 lead-repeat guard.

The numbers in here are measured, not invented. They come from the 14 adjacent
digest pairs in the retained history plus the 2026-08-07/2026-08-08 incident
pair, and the fixture at tests/fixtures/lead_repeat_incident.json is a
sanitized snapshot of the two real scripts. It is a snapshot on purpose:
retention deletes digests, so a test that queried live rows 723/724 would pass
today and vanish later.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.generation.lead_repeat_guard import (
    DEFAULT_THRESHOLD,
    build_rewrite_prompt,
    check_lead_repeat,
    contains_unsupported_numbers,
    extract_lead,
    normalize_lead,
    similarity,
    windowed_similarity,
)

FIXTURE = Path(__file__).parent / "fixtures" / "lead_repeat_incident.json"


@pytest.fixture(scope="module")
def incident():
    return json.loads(FIXTURE.read_text())


# ---------------------------------------------------------------------------
# The incident itself
# ---------------------------------------------------------------------------


def test_incident_pair_trips_the_guard(incident):
    """2026-08-08 opened with 2026-08-07's lead. This is the regression."""
    result = check_lead_repeat(
        incident["aug8"]["script"],
        topic="AI and Technology",
        prior_digests=[{"id": 723, "date": "2026-08-07", "content": incident["aug7"]["script"]}],
    )
    assert result.tripped
    assert result.score > 0.7, f"expected a decisive score, got {result.score:.3f}"
    assert result.matched_digest_id == 723


def test_incident_would_be_missed_by_a_single_wide_window(incident):
    """Why the score is a max across windows and not one number.

    The repeat ends after turn four, so a six-turn window dilutes it below
    threshold. If someone later 'simplifies' this to a single window, this
    test explains what breaks.
    """
    windows = windowed_similarity(incident["aug8"]["script"], incident["aug7"]["script"])
    assert windows["n2"] > DEFAULT_THRESHOLD
    assert windows["n6"] < DEFAULT_THRESHOLD
    assert max(windows.values()) > DEFAULT_THRESHOLD


def test_normal_adjacent_pairs_do_not_trip(incident):
    """13 real adjacent pairs, none of which should fire.

    Worst measured normal score is ~0.17 against a 0.45 threshold.
    """
    for pair in incident["normal_pairs"]:
        result = check_lead_repeat(
            pair["later"],
            topic="AI and Technology",
            prior_digests=[{"id": 1, "date": "x", "content": pair["earlier"]}],
        )
        assert not result.tripped, (
            f"false positive on {pair['label']} at {result.score:.3f}"
        )
        assert result.score < 0.3


# ---------------------------------------------------------------------------
# The two difflib traps that made an earlier draft of this guard useless
# ---------------------------------------------------------------------------


def test_similarity_is_word_wise_not_character_wise():
    """Character-wise comparison + difflib autojunk scores a verbatim repeat
    BELOW an unrelated pair once the strings pass 200 chars. This test pins
    the word-token behavior that fixes it."""
    a = "SPEAKER_1: " + ("the market moved sharply on the news this morning. " * 8)
    b = "SPEAKER_1: " + ("the market moved sharply on the news this morning. " * 8)
    assert similarity(a, b) > 0.99


def test_similarity_ignores_speaker_labels_and_audio_tags():
    a = "SPEAKER_1: [curious] the model shipped today and nobody noticed it at all"
    b = "SPEAKER_2: [amused] the model shipped today and nobody noticed it at all"
    assert similarity(a, b) > 0.95


def test_normalization_strips_the_nightly_welcome_template():
    """The welcome sentence is identical every night and would otherwise
    raise the floor under every comparison."""
    text = "SPEAKER_1: Welcome to the digest, August eighth. I'm Natasha. Real content here."
    assert "welcome to the digest" not in normalize_lead(text)
    assert "real content here" in normalize_lead(text)


# ---------------------------------------------------------------------------
# Lead extraction
# ---------------------------------------------------------------------------


def test_extract_lead_dialogue_takes_leading_turns():
    script = "\n\n".join(f"SPEAKER_{i % 2 + 1}: turn number {i}" for i in range(20))
    lead = extract_lead(script, dialogue=True)
    assert "turn number 0" in lead
    assert "turn number 19" not in lead


def test_extract_lead_narrative_falls_back_to_characters():
    script = "Narrative prose without any speaker labels. " * 100
    lead = extract_lead(script, dialogue=False)
    assert 0 < len(lead) <= 1200


def test_extract_lead_handles_short_and_empty_scripts():
    assert extract_lead("", dialogue=True) == ""
    assert extract_lead("SPEAKER_1: only one turn", dialogue=True).startswith("SPEAKER_1:")


# ---------------------------------------------------------------------------
# Fail-safe behavior
# ---------------------------------------------------------------------------


def test_no_prior_digests_does_not_trip():
    result = check_lead_repeat("SPEAKER_1: anything at all", topic="X", prior_digests=[])
    assert not result.tripped
    assert result.score == 0.0


def test_fetch_failure_returns_untripped(monkeypatch):
    """The guard must never be the reason a digest fails to generate."""
    import src.generation.dedup_pass as dp

    def boom(*a, **k):
        raise RuntimeError("database on fire")

    monkeypatch.setattr(dp, "_fetch_prior_digests", boom)
    result = check_lead_repeat("SPEAKER_1: hello there everyone", topic="X")
    assert not result.tripped


# ---------------------------------------------------------------------------
# Rewrite guardrails
# ---------------------------------------------------------------------------


def test_unsupported_numbers_detected():
    source = "The company grew 18 percent and raised 4 million dollars."
    assert not contains_unsupported_numbers("Growth of 18 percent.", source)
    assert contains_unsupported_numbers("Shares fell 27 percent overnight.", source)


def test_rewrite_prompt_carries_both_leads(incident):
    result = check_lead_repeat(
        incident["aug8"]["script"],
        topic="AI and Technology",
        prior_digests=[{"id": 723, "date": "2026-08-07", "content": incident["aug7"]["script"]}],
    )
    prompt = build_rewrite_prompt(incident["aug8"]["script"], result, dialogue=True)
    assert "do not resemble this" in prompt.lower()
    assert "trillion dollar company" in prompt
    assert "Introduce no new" in prompt


def test_boilerplate_strip_widens_the_margin(incident):
    """Pins the reason normalize_lead removes the welcome template.

    A reviewer measuring with a bare tokenizer got a worst-normal of 0.278
    against this guard's 0.187 and read it as a thinner safety margin. Both
    numbers are correct; the difference is entirely the boilerplate strip,
    which lowers the negatives far more than it lowers the positive. If a
    future tuning pass drops the strip, the margin narrows from ~4.4x to
    ~3.2x and this test says so out loud.
    """
    import difflib
    import re

    from src.generation.lead_repeat_guard import LEAD_TURN_WINDOWS, _lead_at_turns

    def bare_tokens(text):
        return re.findall(r"[a-z0-9']+", text.lower())

    def score(a, b, tokenizer):
        return max(
            difflib.SequenceMatcher(None, tokenizer(_lead_at_turns(a, n)),
                                    tokenizer(_lead_at_turns(b, n)), autojunk=False).ratio()
            for n in LEAD_TURN_WINDOWS
        )

    def worst_normal(tokenizer):
        return max(score(p["earlier"], p["later"], tokenizer) for p in incident["normal_pairs"])

    stripped = worst_normal(lambda t: normalize_lead(t).split())
    unstripped = worst_normal(bare_tokens)

    assert stripped < unstripped, "the boilerplate strip should lower the negatives"
    # Both sides of the comparison, so a regression in either is visible.
    assert stripped < 0.25
    assert unstripped > 0.25

    inc = score(incident["aug7"]["script"], incident["aug8"]["script"],
                lambda t: normalize_lead(t).split())
    assert inc / stripped > 4.0, (
        f"margin over worst normal collapsed: incident {inc:.3f} vs normal {stripped:.3f}"
    )
