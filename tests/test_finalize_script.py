"""finalize_script: the single mandatory post-expansion path (v4.01).

WHY IT EXISTS. v3.48 moved the structural variety pass off the intermediate
expansion iterations to save time and left this comment where the final call
was meant to go:

    # v3.48: Run the final variety pass now if we skipped it during expansion

followed by no code. From 2026-04-24 every digest that expanded shipped
without a variety pass -- four nights out of four in the sampled logs, each
showing 1-5 expansions and exactly one variety pass, always on the draft that
was then discarded and regenerated.

The wiring test at the bottom exists so that cannot happen again silently.
"""
from __future__ import annotations

import pytest

from src.generation.script_generator import ScriptGenerator

SCRIPT = "\n\n".join(f"SPEAKER_{i % 2 + 1}: turn number {i} with some content" for i in range(20))


@pytest.fixture
def generator(monkeypatch):
    gen = object.__new__(ScriptGenerator)
    # No prior digests => the lead-repeat guard never trips, so these tests
    # isolate the variety-pass half.
    monkeypatch.setattr(
        "src.generation.dedup_pass._fetch_prior_digests", lambda **k: []
    )
    return gen


# ---------------------------------------------------------------------------
# Variety pass
# ---------------------------------------------------------------------------


def test_variety_pass_runs_when_the_draft_was_expanded(generator, monkeypatch):
    calls = []
    monkeypatch.setattr(
        ScriptGenerator,
        "_run_structural_variety_pass",
        lambda self, s: calls.append(s) or (s + "\n\nSPEAKER_1: varied"),
    )
    out = generator.finalize_script(SCRIPT, topic="T", already_varied=False)
    assert len(calls) == 1
    assert "varied" in out


def test_variety_pass_skipped_when_the_draft_already_had_one(generator, monkeypatch):
    """No expansion happened, so generate_script already ran it. Running it
    again here would double the nightly call count for no benefit."""
    calls = []
    monkeypatch.setattr(
        ScriptGenerator,
        "_run_structural_variety_pass",
        lambda self, s: calls.append(s) or s,
    )
    generator.finalize_script(SCRIPT, topic="T", already_varied=True)
    assert calls == []


def test_variety_pass_cannot_push_a_script_under_the_hard_floor(generator, monkeypatch):
    """The pass trims 1-2%. A draft that legitimately cleared the floor must
    not be failed by polish applied afterwards."""
    at_floor = "x" * 10_050
    monkeypatch.setattr(
        ScriptGenerator, "_run_structural_variety_pass", lambda self, s: "x" * 9_800
    )
    out = generator.finalize_script(at_floor, topic="T", floor=10_000, already_varied=False)
    assert out == at_floor, "pre-pass draft should be kept when the pass breaches the floor"


def test_variety_pass_result_kept_when_it_stays_above_the_floor(generator, monkeypatch):
    monkeypatch.setattr(
        ScriptGenerator, "_run_structural_variety_pass", lambda self, s: "y" * 20_000
    )
    out = generator.finalize_script("x" * 20_500, topic="T", floor=10_000, already_varied=False)
    assert out == "y" * 20_000


# ---------------------------------------------------------------------------
# Lead-repeat guard integration
# ---------------------------------------------------------------------------


def test_repeat_ships_the_original_when_no_rewrite_is_available(generator, monkeypatch):
    """Fail safe: a logged duplicate beats a failed generation."""
    monkeypatch.setattr(
        "src.generation.dedup_pass._fetch_prior_digests",
        lambda **k: [{"id": 1, "date": "2026-08-07", "content": SCRIPT}],
    )
    monkeypatch.setattr(ScriptGenerator, "_rewrite_repeated_lead", lambda *a, **k: None)
    out = generator.finalize_script(SCRIPT, topic="T", already_varied=True)
    assert out == SCRIPT


def test_repeat_uses_the_rewrite_when_one_is_produced(generator, monkeypatch):
    monkeypatch.setattr(
        "src.generation.dedup_pass._fetch_prior_digests",
        lambda **k: [{"id": 1, "date": "2026-08-07", "content": SCRIPT}],
    )
    monkeypatch.setattr(
        ScriptGenerator, "_rewrite_repeated_lead", lambda *a, **k: "SPEAKER_1: brand new lead"
    )
    out = generator.finalize_script(SCRIPT, topic="T", already_varied=True)
    assert out == "SPEAKER_1: brand new lead"


def test_guard_failure_does_not_break_generation(generator, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("guard exploded")

    monkeypatch.setattr("src.generation.lead_repeat_guard.check_lead_repeat", boom)
    assert generator.finalize_script(SCRIPT, topic="T", already_varied=True) == SCRIPT


def test_empty_script_is_returned_untouched(generator):
    assert generator.finalize_script("", topic="T") == ""


# ---------------------------------------------------------------------------
# Rewrite guardrails
# ---------------------------------------------------------------------------


def test_rewrite_rejected_when_it_invents_a_number(generator, monkeypatch):
    from src.generation import lead_repeat_guard as guard

    monkeypatch.setattr("src.utils.claude_p_health.is_claude_p_healthy", lambda: True)
    monkeypatch.setattr(
        ScriptGenerator,
        "_call_claude_p",
        lambda self, s, u, timeout=360: "SPEAKER_1: " + ("Shares fell 97 percent overnight. " * 12),
    )
    result = guard.check_lead_repeat(
        SCRIPT, topic="T", prior_digests=[{"id": 1, "date": "d", "content": SCRIPT}]
    )
    assert generator._rewrite_repeated_lead(SCRIPT, result, dialogue=True) is None


def test_rewrite_rejected_when_it_loses_speaker_labels(generator, monkeypatch):
    from src.generation import lead_repeat_guard as guard

    monkeypatch.setattr("src.utils.claude_p_health.is_claude_p_healthy", lambda: True)
    monkeypatch.setattr(
        ScriptGenerator,
        "_call_claude_p",
        lambda self, s, u, timeout=360: "plain prose with no labels at all " * 20,
    )
    result = guard.check_lead_repeat(
        SCRIPT, topic="T", prior_digests=[{"id": 1, "date": "d", "content": SCRIPT}]
    )
    assert generator._rewrite_repeated_lead(SCRIPT, result, dialogue=True) is None


def test_rewrite_rejected_when_it_still_repeats(generator, monkeypatch):
    """A rewrite that does not beat the threshold it was written to beat is
    not an improvement worth shipping."""
    from src.generation import lead_repeat_guard as guard

    monkeypatch.setattr("src.utils.claude_p_health.is_claude_p_healthy", lambda: True)
    result = guard.check_lead_repeat(
        SCRIPT, topic="T", prior_digests=[{"id": 1, "date": "d", "content": SCRIPT}]
    )
    # Hand back the offending lead verbatim.
    monkeypatch.setattr(
        ScriptGenerator, "_call_claude_p", lambda self, s, u, timeout=360: result.lead
    )
    assert generator._rewrite_repeated_lead(SCRIPT, result, dialogue=True) is None


# ---------------------------------------------------------------------------
# Wiring. This is the test that would have caught the v3.48 regression.
# ---------------------------------------------------------------------------


def test_create_digest_calls_finalize_script_after_the_expansion_loop():
    import inspect

    src = inspect.getsource(ScriptGenerator.create_digest)
    assert "self.finalize_script(" in src, "create_digest no longer finalizes its script"

    loop_at = src.index("while len(script_content) < TARGET_CHARS")
    floor_at = src.index("below hard floor after expansion")
    finalize_at = src.index("self.finalize_script(")
    assert loop_at < floor_at < finalize_at, (
        "finalize_script must run after the expansion loop AND after the hard-floor "
        "check -- the variety pass trims 1-2% and would otherwise be able to push a "
        "draft that cleared the floor back under it"
    )


# ---------------------------------------------------------------------------
# Expansion-added episodes must not bypass dedup (adversarial review, F7)
# ---------------------------------------------------------------------------


def test_expansion_episode_is_deduped_on_demand(generator, monkeypatch):
    """The pre-dedup pool is capped at MAX_TRANSCRIPTS. Episodes the expansion
    loop reaches beyond that cap were never compared against prior digests and
    used to reach the writer with raw transcripts."""
    import src.generation.transcript_dedup as td

    class _Ep:
        id = 42
        title = "Expansion episode"
        transcript_content = "RAW UNDEDUPED CONTENT " * 100

    monkeypatch.setattr(
        td,
        "dedup_transcript",
        lambda **k: td.TranscriptDedupResult(
            episode_id=42,
            episode_title="Expansion episode",
            original_chars=len(k["transcript"]),
            deduped_chars=20,
            deduped_transcript="CLEANED CONTENT",
        ),
    )

    ep, cache = _Ep(), {}
    generator._dedup_expansion_episode(ep, ["a prior digest script"], cache)
    assert ep.transcript_content == "CLEANED CONTENT"
    assert cache[42] == "CLEANED CONTENT"


def test_expansion_dedup_failure_keeps_the_raw_transcript(generator, monkeypatch):
    """Fail open: a dedup failure must not cost us the episode."""
    import src.generation.transcript_dedup as td

    class _Ep:
        id = 43
        title = "Expansion episode"
        transcript_content = "RAW CONTENT"

    def boom(**k):
        raise RuntimeError("dedup exploded")

    monkeypatch.setattr(td, "dedup_transcript", boom)
    ep, cache = _Ep(), {}
    generator._dedup_expansion_episode(ep, ["prior"], cache)
    assert ep.transcript_content == "RAW CONTENT"
    assert cache == {}


def test_expansion_loop_dedups_cache_misses():
    """Wiring: the loop must not silently pass a cache miss straight through."""
    import inspect

    src = inspect.getsource(ScriptGenerator.create_digest)
    assert "_dedup_expansion_episode(" in src, (
        "expansion-added episodes bypass dedup again"
    )
