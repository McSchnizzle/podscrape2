"""Tests for transcript chunking + chunked dedup (kanban #430).

Covers:
  AC1 -- pure chunking helper (splits at sentence boundaries, lossless,
         single-chunk pass-through under the threshold).
  AC2 -- pipeline wiring: dedup_transcript() calls claude -p once per
         chunk when transcript exceeds MAX_CHUNK_CHARS.
  AC3 -- reassembly preserves order; ANY chunk failure marks the result
         skipped, not silently partial.
  AC4 -- regression test against the 60,735-char fixture (the 5/15
         episode size described in the kanban).
  AC5 -- MAX_TRANSCRIPTS=9 unchanged (sanity test against
         script_generator).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure project root on sys.path so `import src...` works when pytest is
# invoked from anywhere.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.generation import transcript_dedup
from src.generation.transcript_dedup import (
    MAX_CHUNK_CHARS,
    TranscriptDedupResult,
    dedup_transcript,
    split_transcript_into_chunks,
)


FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "transcript_60735.txt"


# ---------------------------------------------------------------------------
# AC1: split_transcript_into_chunks() -- pure helper
# ---------------------------------------------------------------------------


def test_split_no_split_short_text():
    """A 5,000-char string returns a 1-item list equal to the input."""
    text = "Hello world. " * 350  # ~ 4,550 chars
    chunks = split_transcript_into_chunks(text, max_chunk_chars=30_000)
    assert chunks == [text]


def test_split_empty_string():
    """Empty input returns ``[""]`` (NOT ``[]``)."""
    chunks = split_transcript_into_chunks("")
    assert chunks == [""]
    assert "".join(chunks) == ""


def test_split_exact_30k_no_split():
    """Boundary: a string EXACTLY 30,000 chars is a single chunk."""
    text = "x" * 30_000
    chunks = split_transcript_into_chunks(text, max_chunk_chars=30_000)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_split_30001_chars_splits():
    """One char over the threshold forces at least 2 chunks."""
    text = ("This is a sentence. " * 1_600)[:30_001]
    assert len(text) == 30_001
    chunks = split_transcript_into_chunks(text, max_chunk_chars=30_000)
    assert len(chunks) >= 2


def test_split_lossless_on_fixture():
    """Concatenating chunks must reproduce the fixture byte-for-byte."""
    text = FIXTURE_PATH.read_text()
    chunks = split_transcript_into_chunks(text)
    assert "".join(chunks) == text


def test_split_no_chunk_over_max():
    """No chunk exceeds max_chunk_chars when sentence boundaries exist."""
    text = FIXTURE_PATH.read_text()
    chunks = split_transcript_into_chunks(text, max_chunk_chars=10_000)
    # Every chunk must be <= the cap. The chunker either splits at a
    # sentence boundary within the window OR hard-splits at the cap;
    # either way, no chunk should exceed the cap.
    for i, c in enumerate(chunks):
        assert len(c) <= 10_000, f"chunk {i} length {len(c)} > 10000"


def test_split_breaks_at_sentence_boundary():
    """When a sentence boundary exists in the window, chunks end on one."""
    # Construct text where each sentence is 100 chars + ". " -- many
    # boundaries per 30k window. The chunker should land each cut on a
    # ". " boundary except possibly the final chunk.
    sentence = ("A" * 98) + ". "  # 100 chars
    text = sentence * 400  # 40,000 chars
    chunks = split_transcript_into_chunks(text, max_chunk_chars=30_000)
    assert len(chunks) >= 2
    # All but the last chunk should end with ". " (sentence + trailing space)
    for i, c in enumerate(chunks[:-1]):
        assert c.endswith(". "), (
            f"chunk {i} did not end on a sentence boundary: ...{c[-20:]!r}"
        )
    # Lossless
    assert "".join(chunks) == text


def test_split_handles_no_sentence_boundary():
    """If a chunk window has no sentence boundary, hard-split at the cap."""
    text = "x" * 60_000  # zero sentence-end characters
    chunks = split_transcript_into_chunks(text, max_chunk_chars=30_000)
    assert len(chunks) == 2
    assert len(chunks[0]) == 30_000
    assert len(chunks[1]) == 30_000
    assert "".join(chunks) == text


def test_split_invalid_max_chunk_chars():
    """Zero or negative max_chunk_chars raises ValueError."""
    with pytest.raises(ValueError):
        split_transcript_into_chunks("hello", max_chunk_chars=0)
    with pytest.raises(ValueError):
        split_transcript_into_chunks("hello", max_chunk_chars=-1)


def test_split_question_and_exclamation_boundaries():
    """`?` and `!` followed by whitespace also count as sentence boundaries."""
    text = ("Question? " * 100) + ("Exciting! " * 100) + ("Statement. " * 100)
    # Choose a max small enough to force a split inside the questions/exclaims
    chunks = split_transcript_into_chunks(text, max_chunk_chars=500)
    assert len(chunks) >= 3
    assert "".join(chunks) == text
    for i, c in enumerate(chunks[:-1]):
        # Each non-final chunk must end on a `?`, `!`, or `.` followed by a space.
        # (The chunker leaves the trailing space at the end of the chunk.)
        assert c[-2:] in {"? ", "! ", ". "}, (
            f"chunk {i} ended with {c[-5:]!r}, not on a sentence boundary"
        )


# ---------------------------------------------------------------------------
# AC4: 60,735-char fixture regression
# ---------------------------------------------------------------------------


def test_60735_fixture_loaded_and_chunked():
    """Fixture is exactly 60,735 chars and splits into >=2 chunks."""
    text = FIXTURE_PATH.read_text()
    assert len(text) == 60_735, f"fixture size drifted to {len(text)}"
    chunks = split_transcript_into_chunks(text)
    # 60_735 / 30_000 -> minimum 3 chunks (last chunk may be small)
    assert 2 <= len(chunks) <= 4, f"unexpected chunk count {len(chunks)}"
    # Lossless
    assert "".join(chunks) == text
    # Every non-final chunk should be <=30k
    for c in chunks[:-1]:
        assert len(c) <= MAX_CHUNK_CHARS


# ---------------------------------------------------------------------------
# AC2/AC3: dedup_transcript() wiring with mocked claude -p
# ---------------------------------------------------------------------------


class _DummyEpisode:
    """Minimal stand-in matching Episode duck-type for dedup_transcript."""

    def __init__(self, ep_id, title, transcript_content):
        self.id = ep_id
        self.title = title
        self.transcript_content = transcript_content


def _patch_claude_healthy(monkeypatch):
    """Force claude -p health check to return True so dedup_transcript runs."""
    # The health check is imported inside dedup_transcript; patch at the
    # source module so the import in dedup_transcript picks up the stub.
    import importlib

    health = importlib.import_module("src.utils.claude_p_health")
    monkeypatch.setattr(health, "is_claude_p_healthy", lambda: True)


def test_dedup_transcript_single_call_under_30k(monkeypatch):
    """Transcript <= 30k chars must result in exactly 1 claude -p call.

    kanban #2861: the fake output is sized above the safety-net floor so
    this test isolates chunking/call-count behavior from the separate
    below-floor restore behavior (covered by its own tests below).
    """
    _patch_claude_healthy(monkeypatch)

    transcript = ("This is a sentence about something interesting. " * 500)  # ~24.5k
    assert len(transcript) < MAX_CHUNK_CHARS

    call_count = {"n": 0}
    cleaned_output = "CLEANED_OUTPUT. " * 300  # ~4.8k, well above the floor

    def fake_call(prompt, timeout=300):
        call_count["n"] += 1
        return cleaned_output

    monkeypatch.setattr(transcript_dedup, "_call_claude_p", fake_call)

    result = dedup_transcript(
        transcript=transcript,
        episode_title="Short ep",
        episode_id=1,
        prior_content="some prior content",
    )

    assert call_count["n"] == 1
    assert result.skipped is False
    assert result.below_floor_action is None
    assert result.deduped_transcript == cleaned_output
    assert result.original_chars == len(transcript)
    assert result.deduped_chars == len(cleaned_output)


def test_dedup_transcript_chunks_when_over_30k(monkeypatch):
    """Transcript > 30k chars triggers >=2 claude -p calls, results ordered.

    kanban #2861: each fake chunk output is bulked up above the safety-net
    floor (in aggregate) so this test isolates chunk ordering/reassembly
    from the separate below-floor restore behavior (covered by its own
    tests below).
    """
    _patch_claude_healthy(monkeypatch)

    transcript = FIXTURE_PATH.read_text()
    assert len(transcript) > MAX_CHUNK_CHARS

    calls = []

    def fake_call(prompt, timeout=300):
        idx = len(calls) + 1
        calls.append(prompt)
        return f"[CLEAN-{idx}] " + ("Novel filler content. " * 200)

    monkeypatch.setattr(transcript_dedup, "_call_claude_p", fake_call)

    result = dedup_transcript(
        transcript=transcript,
        episode_title="Long ep 5/15",
        episode_id=42,
        prior_content="prior content here",
    )

    # Expect at least 2 chunks given the fixture size.
    assert len(calls) >= 2
    assert result.skipped is False
    # Cleaned output contains every chunk's marker, in order.
    expected_markers = [f"[CLEAN-{i}]" for i in range(1, len(calls) + 1)]
    last_pos = -1
    for marker in expected_markers:
        pos = result.deduped_transcript.find(marker)
        assert pos > last_pos, (
            f"marker {marker} not found after position {last_pos} in "
            f"output: {result.deduped_transcript[:200]!r}"
        )
        last_pos = pos
    # Episode title should appear with part markers in each prompt's
    # transcript header.
    for i, prompt in enumerate(calls, start=1):
        assert f"part {i}/{len(calls)}" in prompt, (
            f"prompt {i} missing part marker"
        )


def test_dedup_transcript_chunk_failure_marks_skipped(monkeypatch):
    """If ANY chunk fails, the whole dedup returns skipped (no partials)."""
    _patch_claude_healthy(monkeypatch)

    transcript = FIXTURE_PATH.read_text()

    calls = {"n": 0}

    def fake_call(prompt, timeout=300):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("claude -p exploded on chunk 2")
        return "[CLEAN]"

    monkeypatch.setattr(transcript_dedup, "_call_claude_p", fake_call)

    result = dedup_transcript(
        transcript=transcript,
        episode_title="Failing chunk ep",
        episode_id=99,
        prior_content="prior",
    )

    assert result.skipped is True
    assert "chunk" in result.skip_reason.lower()
    # Original transcript is preserved when we skip
    assert result.deduped_transcript == transcript
    assert result.deduped_chars == len(transcript)


def test_dedup_transcript_chunk_timeout_marks_skipped(monkeypatch):
    """Timeout on any chunk marks the whole dedup skipped with 'timeout'."""
    _patch_claude_healthy(monkeypatch)

    transcript = FIXTURE_PATH.read_text()

    calls = {"n": 0}

    def fake_call(prompt, timeout=300):
        calls["n"] += 1
        if calls["n"] == 1:
            raise subprocess.TimeoutExpired(cmd="claude", timeout=timeout)
        return "[CLEAN]"

    monkeypatch.setattr(transcript_dedup, "_call_claude_p", fake_call)

    result = dedup_transcript(
        transcript=transcript,
        episode_title="Timeout ep",
        episode_id=100,
        prior_content="prior",
    )

    assert result.skipped is True
    assert "timeout" in result.skip_reason.lower()
    assert result.deduped_transcript == transcript


def test_dedup_transcript_no_new_content_in_one_chunk(monkeypatch):
    """`[NO_NEW_CONTENT]` from one chunk drops that chunk only, not others.

    kanban #2861: surviving chunks' fake output is bulked up above the
    safety-net floor (in aggregate) so this test isolates per-chunk
    sentinel handling from the separate below-floor restore behavior.
    """
    _patch_claude_healthy(monkeypatch)

    transcript = FIXTURE_PATH.read_text()

    calls = {"n": 0}

    def fake_call(prompt, timeout=300):
        calls["n"] += 1
        if calls["n"] == 1:
            return "[NO_NEW_CONTENT]"
        return f"chunk{calls['n']} novel content. " * 300

    monkeypatch.setattr(transcript_dedup, "_call_claude_p", fake_call)

    result = dedup_transcript(
        transcript=transcript,
        episode_title="Mixed-novelty ep",
        episode_id=101,
        prior_content="prior",
    )

    assert result.skipped is False
    # Chunk 1's output was emptied; chunk 2's survives.
    assert "[NO_NEW_CONTENT]" not in result.deduped_transcript
    assert "chunk2 novel content" in result.deduped_transcript


def test_dedup_transcript_all_chunks_no_new_content(monkeypatch):
    """If every chunk returns the sentinel, the deduped output is empty."""
    _patch_claude_healthy(monkeypatch)

    transcript = FIXTURE_PATH.read_text()

    def fake_call(prompt, timeout=300):
        return "[NO_NEW_CONTENT]"

    monkeypatch.setattr(transcript_dedup, "_call_claude_p", fake_call)

    result = dedup_transcript(
        transcript=transcript,
        episode_title="Fully-redundant ep",
        episode_id=102,
        prior_content="prior",
    )

    assert result.skipped is False
    assert result.deduped_transcript == ""
    assert result.deduped_chars == 0


# ---------------------------------------------------------------------------
# AC5: MAX_TRANSCRIPTS=9 unchanged
# ---------------------------------------------------------------------------


def test_max_transcripts_constant_unchanged():
    """The script generator's MAX_TRANSCRIPTS must remain 9 (kanban #430 AC5).

    This is a defensive guard: future refactors should not silently change
    the upstream episode cap when touching the dedup pipeline.
    """
    sg_path = PROJECT_ROOT / "src" / "generation" / "script_generator.py"
    src = sg_path.read_text()
    # Find the canonical assignment and assert the value.
    assert "MAX_TRANSCRIPTS = 9" in src, (
        "MAX_TRANSCRIPTS must remain 9 per kanban #430 AC5"
    )


# ---------------------------------------------------------------------------
# kanban #2861: dedup over-stripping safety net
#
# Bug: episode 19 ("Claude Sonnet 5 is a Disappointment", 6,980 chars) argued
# its contrarian verdict FROM benchmark numbers that also appeared
# (positively) in earlier episodes 84/85 in the same batch. The old dedup
# rule ("remove repeated benchmark numbers already in PRIOR CONTENT")
# stripped ep19 6,980 -> 218 chars, leaving a bare, unsupported assertion
# that the writer then hedged on-air ("though we don't have the full detail
# on why"). These tests cover the safety net that prevents that: a non-empty
# but below-floor dedup result gets a bounded original excerpt restored
# instead; a genuinely empty result gets dropped (not restored) and excluded
# from writer input.
# ---------------------------------------------------------------------------

from src.generation.transcript_dedup import (
    MIN_DEDUPED_CHARS,
    MIN_RETENTION_PCT,
    RESTORE_EXCERPT_CAP_CHARS,
    dedup_episode_batch,
    _restore_bounded_excerpt,
)


# ---------------------------------------------------------------------------
# _restore_bounded_excerpt() -- pure helper
# ---------------------------------------------------------------------------


def test_restore_bounded_excerpt_short_original_returned_unchanged():
    """An original at or under the cap is returned verbatim."""
    text = "Short original transcript. " * 10  # well under the 3k cap
    assert _restore_bounded_excerpt(text) == text


def test_restore_bounded_excerpt_caps_and_trims_at_sentence_boundary():
    """A long original is capped and trimmed to the last sentence boundary."""
    sentence = ("A" * 98) + ". "  # 100 chars, matches chunker's own fixture style
    text = sentence * 100  # 10,000 chars, well over the 3k cap
    excerpt = _restore_bounded_excerpt(text, cap=3_000)
    assert len(excerpt) <= 3_000
    assert excerpt.endswith(". ")
    assert text.startswith(excerpt)


def test_restore_bounded_excerpt_hard_cuts_with_no_boundary():
    """No sentence boundary in the window -- hard cut at the cap."""
    text = "x" * 10_000
    excerpt = _restore_bounded_excerpt(text, cap=3_000)
    assert len(excerpt) == 3_000


def test_restore_bounded_excerpt_ignores_early_boundary_below_floor():
    """codex review (kanban #2861 round 2): a sentence boundary EARLY in the
    window (e.g. a short opening line) must never win over the floor
    guarantee -- that recreates the exact below-floor stub this function
    exists to prevent. Codex's exact probe: "Done. " (a boundary at char 6)
    followed by thousands of unpunctuated chars restored to only 6 chars
    under the old implementation."""
    text = "Done. " + ("x" * 6_994)  # 7,000 chars total, one EARLY boundary
    assert len(text) > RESTORE_EXCERPT_CAP_CHARS
    excerpt = _restore_bounded_excerpt(text)
    assert len(excerpt) >= MIN_DEDUPED_CHARS
    # No boundary exists at/after the floor within the window -- must hard
    # cut at the cap, NOT stop at the 6-char early boundary.
    assert len(excerpt) == RESTORE_EXCERPT_CAP_CHARS


def test_restore_bounded_excerpt_uses_boundary_at_or_after_floor():
    """When a REAL sentence boundary exists between the floor and the cap,
    use it (sentence-trimmed) rather than hard-cutting -- while still
    skipping any earlier boundary before the floor."""
    early = "Done. "  # boundary at char 6 -- must be ignored (below floor)
    filler_to_floor = "x" * 700  # pushes well past MIN_DEDUPED_CHARS (500)
    late_boundary = "Stop here. "  # a real boundary AFTER the floor
    tail = "y" * 3_000  # keeps total > cap so the cap/trim logic actually runs
    text = early + filler_to_floor + late_boundary + tail
    assert len(text) > 3_000

    excerpt = _restore_bounded_excerpt(text, cap=3_000)

    assert len(excerpt) >= MIN_DEDUPED_CHARS
    assert excerpt.endswith("Stop here. ")
    assert text.startswith(excerpt)


def test_restore_bounded_excerpt_clamps_cap_below_floor(monkeypatch):
    """codex review round 3: the helper doesn't literally guarantee >=floor
    for a caller that passes cap < floor. Clamp cap up to floor internally
    so the >= floor guarantee holds regardless of caller, rather than
    relying on every current/future caller to pass a sane cap."""
    text = "x" * 10_000
    # cap (100) is well below floor (500) -- must not silently return a
    # 100-char (or shorter) excerpt.
    excerpt = _restore_bounded_excerpt(text, cap=100, floor=500)
    assert len(excerpt) >= 500


def test_restore_bounded_excerpt_default_cap_and_floor_are_module_constants():
    """Sanity guard: RESTORE_EXCERPT_CAP_CHARS > MIN_DEDUPED_CHARS must hold
    for the module's own default cap/floor pairing -- the clamp above is a
    defensive fallback for unusual callers, not a substitute for keeping
    the production defaults sane."""
    assert RESTORE_EXCERPT_CAP_CHARS > MIN_DEDUPED_CHARS


# ---------------------------------------------------------------------------
# dedup_transcript() floor/restore/drop behavior
# ---------------------------------------------------------------------------


def _ep19_style_original() -> str:
    """A transcript that argues a thesis from benchmark evidence, long
    enough that an over-aggressive dedup pass plausibly reduces it far
    below the safety-net floor -- mirrors the real ep19 case (6,980 chars
    original, 218-char over-stripped output)."""
    thesis = (
        "Sonnet 5 is a disappointment. The benchmark numbers tell the story: "
        "on the coding eval it scored well behind the field, and on the "
        "reasoning suite the gap was even wider. "
    )
    return thesis * 60  # a few thousand chars, comfortably under 30k


def test_dedup_transcript_below_floor_restores_original_excerpt(monkeypatch):
    """A non-empty but below-floor dedup result triggers a restore from the
    ORIGINAL transcript, not the over-stripped stub."""
    _patch_claude_healthy(monkeypatch)

    original = _ep19_style_original()
    assert len(original) > MIN_DEDUPED_CHARS * 4  # comfortably over the floor

    stub = "Sonnet 5 is a disappointment."  # 30 chars -- the over-stripped bug case
    assert len(stub) < MIN_DEDUPED_CHARS

    monkeypatch.setattr(transcript_dedup, "_call_claude_p", lambda prompt, timeout=300: stub)

    result = dedup_transcript(
        transcript=original,
        episode_title="Claude Sonnet 5 is a Disappointment",
        episode_id=19,
        prior_content="prior digests praising Sonnet 5's benchmarks",
    )

    assert result.skipped is False
    assert result.below_floor_action == "restored"
    # The writer never sees the below-floor stub.
    assert result.deduped_transcript != stub
    assert len(result.deduped_transcript) >= MIN_DEDUPED_CHARS
    # It's a real excerpt of the ORIGINAL transcript, not a fabrication.
    assert original.startswith(result.deduped_transcript)
    assert len(result.deduped_transcript) <= RESTORE_EXCERPT_CAP_CHARS


def test_dedup_transcript_at_floor_not_restored(monkeypatch):
    """A dedup result at/above the floor is left as the model's own output."""
    _patch_claude_healthy(monkeypatch)

    original = _ep19_style_original()
    # Comfortably above both MIN_DEDUPED_CHARS and MIN_RETENTION_PCT of original.
    # v4.01: the kept text must be drawn from the ORIGINAL. The dedup pass is a
    # removal pass and its output is now provenance-checked against the input,
    # so a mock returning invented prose is rejected in favor of the raw chunk
    # and this test would be asserting against the wrong string.
    kept = (
        "Sonnet 5 is a disappointment. The benchmark numbers tell the story: "
        "on the coding eval it scored well behind the field, and on the "
        "reasoning suite the gap was even wider. "
    ) * 30
    assert kept in original  # every sentence really is the source's
    assert len(kept) >= MIN_DEDUPED_CHARS
    assert len(kept) / len(original) >= MIN_RETENTION_PCT

    monkeypatch.setattr(transcript_dedup, "_call_claude_p", lambda prompt, timeout=300: kept)

    result = dedup_transcript(
        transcript=original,
        episode_title="Healthy dedup ep",
        episode_id=20,
        prior_content="prior content",
    )

    assert result.below_floor_action is None
    assert result.deduped_transcript == kept


def test_dedup_transcript_zero_content_drops_not_restores(monkeypatch):
    """[NO_NEW_CONTENT] is a genuine drop, never a restore -- there's nothing
    to restore evidence FOR when the episode has no distinct angle at all."""
    _patch_claude_healthy(monkeypatch)

    original = _ep19_style_original()
    monkeypatch.setattr(
        transcript_dedup, "_call_claude_p", lambda prompt, timeout=300: "[NO_NEW_CONTENT]"
    )

    result = dedup_transcript(
        transcript=original,
        episode_title="Fully redundant ep",
        episode_id=21,
        prior_content="prior content covering everything in this episode",
    )

    assert result.below_floor_action == "dropped"
    assert result.deduped_chars == 0
    assert result.deduped_transcript == ""


def test_dedup_transcript_too_short_original_marks_dropped(monkeypatch):
    """codex review (kanban #2861 round 2): an original transcript below the
    floor bypassed the safety net entirely -- skipped=True with the full,
    too-short original handed back as deduped_transcript and no signal for
    the caller to exclude it. Now it must set below_floor_action='dropped'
    (even while skipped=True -- dedup never ran) so script_generator
    excludes it from writer input, same as a genuinely-redundant result."""
    _patch_claude_healthy(monkeypatch)

    tiny_original = "Too short to be a real segment. " * 10  # ~330 chars
    assert len(tiny_original) < MIN_DEDUPED_CHARS

    calls = {"n": 0}

    def fake_call(prompt, timeout=300):
        calls["n"] += 1
        return "should never be called"

    monkeypatch.setattr(transcript_dedup, "_call_claude_p", fake_call)

    result = dedup_transcript(
        transcript=tiny_original,
        episode_title="Tiny original ep",
        episode_id=200,
        prior_content="prior content",
    )

    assert calls["n"] == 0  # too short to bother calling claude -p at all
    assert result.skipped is True
    assert result.skip_reason == "transcript too short"
    assert result.below_floor_action == "dropped"


# ---------------------------------------------------------------------------
# dedup_episode_batch() -- thesis preservation across siblings + batch counts
# ---------------------------------------------------------------------------


class _ThesisEpisode:
    """Duck-type Episode: a short episode whose supporting facts overlap
    longer sibling episodes earlier in the same batch."""

    def __init__(self, ep_id, title, transcript_content):
        self.id = ep_id
        self.title = title
        self.transcript_content = transcript_content


def test_batch_restores_thesis_when_over_stripped_by_siblings(monkeypatch):
    """Mirrors the real bug: two longer sibling episodes share benchmark
    facts that a short, contrarian episode's thesis depends on. If dedup
    over-strips the contrarian episode's supporting evidence, the safety
    net restores a bounded original excerpt -- the writer never receives a
    below-floor stub."""
    _patch_claude_healthy(monkeypatch)

    ep_siblings_a = _ThesisEpisode(84, "Episode 84", "Sibling content A. " * 300)
    ep_siblings_b = _ThesisEpisode(85, "Episode 85", "Sibling content B. " * 300)
    ep_contrarian = _ThesisEpisode(19, "Claude Sonnet 5 is a Disappointment", _ep19_style_original())

    # Match on unique RAW transcript content, NOT episode titles: prior_content
    # accumulates "--- ALREADY SELECTED: <title> ---" headers for every prior
    # episode, so a later episode's own prompt contains EARLIER episodes'
    # titles too (matching on title would misfire on the contrarian episode's
    # own call once siblings A/B have already run).
    def fake_call(prompt, timeout=300):
        # Siblings dedup normally (plenty of novel framing survives).
        # v4.01: returned text must come from the sibling's own transcript --
        # output is provenance-checked against the input chunk.
        if "Sibling content A." in prompt:
            return "Sibling content A. " * 50
        if "Sibling content B." in prompt:
            return "Sibling content B. " * 50
        # The contrarian episode gets over-stripped by the (buggy) model
        # behavior this safety net exists to catch.
        return "Sonnet 5 is a disappointment."

    monkeypatch.setattr(transcript_dedup, "_call_claude_p", fake_call)

    results, combined = dedup_episode_batch(
        episodes=[ep_siblings_a, ep_siblings_b, ep_contrarian],
        prior_digest_scripts=["some prior digest script"],
    )

    contrarian_result = next(r for r in results if r.episode_id == 19)
    assert contrarian_result.below_floor_action == "restored"
    assert contrarian_result.deduped_chars >= MIN_DEDUPED_CHARS

    # The writer-facing combined content for episode 19 is the restored
    # excerpt, not the bare stub the buggy dedup pass returned.
    ep19_block_start = combined.find("--- EPISODE: Claude Sonnet 5 is a Disappointment ---")
    assert ep19_block_start != -1
    ep19_block = combined[ep19_block_start:]
    assert ep19_block.strip() != (
        "--- EPISODE: Claude Sonnet 5 is a Disappointment ---\n"
        "Sonnet 5 is a disappointment."
    )
    assert contrarian_result.deduped_transcript in combined
    assert len(contrarian_result.deduped_transcript) >= MIN_DEDUPED_CHARS


def test_batch_drops_genuinely_redundant_episode_not_present_as_stub(monkeypatch):
    """When an episode truly has nothing new (not just over-stripped), it is
    dropped from the writer input entirely -- absent, not a stub."""
    _patch_claude_healthy(monkeypatch)

    ep_sibling = _ThesisEpisode(84, "Episode 84", "Sibling content. " * 300)
    ep_redundant = _ThesisEpisode(19, "Fully covered episode", _ep19_style_original())

    # Match on unique RAW transcript content -- see comment in
    # test_batch_restores_thesis_when_over_stripped_by_siblings for why
    # title-based matching misfires once prior_content accumulates titles.
    def fake_call(prompt, timeout=300):
        if "Sibling content." in prompt:
            return "Sibling novel framing. " * 50
        return "[NO_NEW_CONTENT]"

    monkeypatch.setattr(transcript_dedup, "_call_claude_p", fake_call)

    results, combined = dedup_episode_batch(
        episodes=[ep_sibling, ep_redundant],
        prior_digest_scripts=["some prior digest script"],
    )

    redundant_result = next(r for r in results if r.episode_id == 19)
    assert redundant_result.below_floor_action == "dropped"
    assert redundant_result.deduped_chars == 0
    # Absent from writer input entirely -- no episode-19 block at all.
    assert "Fully covered episode" not in combined


def test_batch_complete_counts_include_below_floor_drops(monkeypatch, caplog):
    """The batch-complete summary's redundant/drop count must include
    below-floor drops (deduped_chars == 0), and separately surface restores."""
    _patch_claude_healthy(monkeypatch)

    # Distinct raw-content markers (not titles -- see comment in
    # test_batch_restores_thesis_when_over_stripped_by_siblings) so each
    # episode's own transcript-to-clean prompt is unambiguous even after
    # prior_content accumulates earlier episodes' titles/output.
    # v4.01: the match marker must appear in the episode's RAW transcript but
    # NOT in the text the mock returns. Sibling content now genuinely reaches
    # later prompts (it used to be truncated away), so a marker that survives
    # into the output would make this branch fire for every later episode too.
    ep_kept = _ThesisEpisode(1, "Kept episode", "Novel content. " * 300 + "KEEP_MARKER")
    ep_restored = _ThesisEpisode(2, "Restored episode", _ep19_style_original() + " RESTORE_MARKER")
    ep_dropped = _ThesisEpisode(3, "Dropped episode", _ep19_style_original() + " DROP_MARKER")

    def fake_call(prompt, timeout=300):
        if "KEEP_MARKER" in prompt:
            # v4.01: drawn from the episode's own transcript so the
            # provenance check accepts it (see dedup_transcript).
            return "Novel content. " * 100
        if "RESTORE_MARKER" in prompt:
            return "Tiny stub."  # below floor -> restored
        return "[NO_NEW_CONTENT]"  # Dropped episode -> genuinely empty

    monkeypatch.setattr(transcript_dedup, "_call_claude_p", fake_call)

    import logging

    caplog.set_level(logging.INFO, logger="src.generation.transcript_dedup")
    results, _ = dedup_episode_batch(
        episodes=[ep_kept, ep_restored, ep_dropped],
        prior_digest_scripts=["some prior digest script"],
    )

    empty_count = sum(1 for r in results if r.deduped_chars == 0 and not r.skipped)
    dropped_count = sum(1 for r in results if r.below_floor_action == "dropped")
    restored_count = sum(1 for r in results if r.below_floor_action == "restored")

    assert empty_count == 1
    # In THIS scenario (no too-short-original episodes) every below-floor
    # drop happens to be a zero-char result too. That equality does NOT
    # hold in general once a too-short-original episode is involved --
    # see test_batch_complete_counts_include_too_short_original_drops.
    assert dropped_count == empty_count
    assert restored_count == 1

    summary_lines = [rec.message for rec in caplog.records if "batch complete" in rec.message]
    assert summary_lines, "expected a 'Pre-gen dedup batch complete' summary log line"
    assert "1 fully redundant/dropped" in summary_lines[-1]
    assert "1 restored" in summary_lines[-1]


def test_batch_complete_counts_include_too_short_original_drops(monkeypatch, caplog):
    """codex review (kanban #2861 round 2): the batch-complete 'dropped'
    count must include too-short-original drops (skipped=True, nonzero
    original_chars), not just deduped-to-zero drops. The old `empty`
    counter (deduped_chars==0 and not skipped) silently missed this case --
    below_floor_action is the only field that captures both."""
    _patch_claude_healthy(monkeypatch)

    ep_kept = _ThesisEpisode(70, "Kept episode", "Novel content. " * 300)
    ep_tiny = _ThesisEpisode(71, "Tiny episode", "Too short. " * 5)
    assert len(ep_tiny.transcript_content) < MIN_DEDUPED_CHARS

    monkeypatch.setattr(
        transcript_dedup,
        "_call_claude_p",
        lambda prompt, timeout=300: "Genuinely novel material not covered anywhere else. " * 30,
    )

    import logging

    caplog.set_level(logging.INFO, logger="src.generation.transcript_dedup")
    results, combined = dedup_episode_batch(
        episodes=[ep_kept, ep_tiny],
        prior_digest_scripts=["some prior digest script"],
    )

    tiny_result = next(r for r in results if r.episode_id == 71)
    assert tiny_result.skipped is True
    assert tiny_result.below_floor_action == "dropped"
    # The old `empty` counter would have missed this -- it's skipped=True
    # with a nonzero original_chars, not a zero-char dedup result.
    empty_count = sum(1 for r in results if r.deduped_chars == 0 and not r.skipped)
    dropped_count = sum(1 for r in results if r.below_floor_action == "dropped")
    assert empty_count == 0
    assert dropped_count == 1

    summary_lines = [rec.message for rec in caplog.records if "batch complete" in rec.message]
    assert summary_lines
    assert "1 fully redundant/dropped" in summary_lines[-1]
    assert "--- EPISODE: Tiny episode ---" not in combined


# ---------------------------------------------------------------------------
# Behavioral regressions (codex round 2): assert the actual WRITER-FACING
# combined string never contains a below-floor fragment. Source-text
# assertions alone did not catch the restore-boundary bug (finding #1) or
# the too-short-original bypass (finding #3) -- these exercise the full
# dedup_episode_batch() -> combined pipeline the writer actually consumes.
# ---------------------------------------------------------------------------


def test_batch_combined_never_contains_below_floor_restore_fragment(monkeypatch):
    """Regression for the restore-boundary bug: an original transcript with
    an EARLY sentence boundary (the exact shape that broke the old
    _restore_bounded_excerpt) must still produce a floor-respecting excerpt
    in the writer-facing combined string, not a several-char fragment."""
    _patch_claude_healthy(monkeypatch)

    # Early boundary at char 11 ("Confirmed. "), then thousands of chars
    # with no further punctuation.
    original = "Confirmed. " + ("Sonnet 5 underperforms across every eval " * 200)
    assert len(original) > RESTORE_EXCERPT_CAP_CHARS

    ep = _ThesisEpisode(50, "Early-boundary episode", original)

    monkeypatch.setattr(
        transcript_dedup, "_call_claude_p", lambda prompt, timeout=300: "Confirmed."
    )

    results, combined = dedup_episode_batch(
        episodes=[ep],
        prior_digest_scripts=["some prior digest script"],
    )

    result = results[0]
    assert result.below_floor_action == "restored"
    assert result.deduped_chars >= MIN_DEDUPED_CHARS

    assert "--- EPISODE: Early-boundary episode ---" in combined
    # The writer-facing content is the full restored excerpt, not the
    # 11-char "Confirmed." stub the mocked model returned.
    assert result.deduped_transcript in combined
    assert len(result.deduped_transcript) >= MIN_DEDUPED_CHARS


def test_batch_combined_excludes_too_short_original_episode(monkeypatch):
    """Regression for the too-short-original bypass: an episode whose
    ORIGINAL transcript is under the floor must be completely ABSENT from
    the writer-facing combined string -- not present as a below-floor stub."""
    _patch_claude_healthy(monkeypatch)

    ep_normal = _ThesisEpisode(60, "Normal episode", "Real substantial content. " * 100)
    ep_tiny = _ThesisEpisode(61, "Tiny original episode", "Way too short. " * 5)
    assert len(ep_tiny.transcript_content) < MIN_DEDUPED_CHARS

    monkeypatch.setattr(
        transcript_dedup,
        "_call_claude_p",
        lambda prompt, timeout=300: "Novel content not covered elsewhere. " * 30,
    )

    results, combined = dedup_episode_batch(
        episodes=[ep_normal, ep_tiny],
        prior_digest_scripts=["some prior digest script"],
    )

    tiny_result = next(r for r in results if r.episode_id == 61)
    assert tiny_result.below_floor_action == "dropped"
    assert tiny_result.skipped is True  # dedup never ran -- too short to bother

    # Completely absent from writer input -- no episode block, no stub text.
    assert "--- EPISODE: Tiny original episode ---" not in combined
    assert "Way too short." not in combined
    # The normal episode is unaffected.
    assert "--- EPISODE: Normal episode ---" in combined


# ---------------------------------------------------------------------------
# script_generator.py cleanup wiring (kanban #2861)
# ---------------------------------------------------------------------------


def _slice_between(src: str, start_marker: str, end_marker: str) -> str:
    start = src.index(start_marker)
    end = src.index(end_marker, start)
    return src[start:end]


def test_script_generator_prompts_no_false_completeness_claims():
    """The dialogue/narrative writer prompts must not claim COMPLETE/full
    access or that transcripts are inherently self-supporting -- codex
    review (kanban #2861 round 2) flagged that those claims are false for
    deduped content, below-floor-restored excerpts, dedup-skipped originals,
    and no-prior-script runs. Scoped to the dialogue and narrative
    prompt-building methods specifically via source slicing between known
    method boundaries -- NOT a whole-file check, because the separate
    _generate_general_summary_script path intentionally keeps the old
    language (see test_general_summary_path_unaffected_by_prompt_cleanup)."""
    sg_path = PROJECT_ROOT / "src" / "generation" / "script_generator.py"
    src = sg_path.read_text()

    dialogue_src = _slice_between(
        src, "def _generate_dialogue_script(", "def _enforce_speaker_name_binding("
    )
    narrative_src = _slice_between(
        src, "def _generate_narrative_script(", "def _run_dedup_pass_with_retry("
    )

    for label, section in [("dialogue", dialogue_src), ("narrative", narrative_src)]:
        assert "COMPLETE access" not in section, f"{label} prompt still claims COMPLETE access"
        assert "is complete and" not in section, f"{label} prompt still claims completeness"
        assert "self-supporting" not in section, f"{label} prompt still claims self-supporting"
        assert "full transcripts" not in section, f"{label} prompt still claims full transcripts"
        assert "the key insights are present" not in section
        assert "content was truncated for length" not in section
        # The truthful replacement should be present.
        assert "actual content" in section, f"{label} prompt missing truthful replacement"


def test_general_summary_path_unaffected_by_prompt_cleanup():
    """_generate_general_summary_script never goes through
    dedup_episode_batch (confirmed via call-graph: create_general_summary
    doesn't call it) -- it's a separate, out-of-scope path. Pin that the
    cleanup above did NOT touch it, so a future refactor doesn't
    accidentally couple the two prompt-cleanup concerns."""
    sg_path = PROJECT_ROOT / "src" / "generation" / "script_generator.py"
    src = sg_path.read_text()
    general_src = _slice_between(
        src, "def _generate_general_summary_script(", "def mark_episode_as_digested("
    )
    assert "COMPLETE access" in general_src


def test_script_generator_marks_dropped_episodes_as_digested():
    """Episodes the safety net drops for zero novel content must still be
    marked digested (covered by siblings) so they don't resurface tomorrow
    only to be re-deduped to nothing again."""
    sg_path = PROJECT_ROOT / "src" / "generation" / "script_generator.py"
    src = sg_path.read_text()
    assert "dropped_episode_ids" in src
    assert "mark_episode_as_digested(dropped_ep)" in src


def test_script_generator_drop_check_precedes_and_is_independent_of_skipped():
    """codex round 2, finding #3: the below-floor drop check in
    create_digest's dedup-caching loop must be evaluated BEFORE (and
    independent of) `not result.skipped`, so a too-short-original result
    (skipped=True, below_floor_action='dropped') is still excluded from
    writer input rather than falling through to the "keep original,
    untouched" fallback meant for transient dedup failures. This is a
    structural/wiring check; the actual invariant is proven behaviorally by
    test_batch_combined_excludes_too_short_original_episode at the dedup
    module level (script_generator's role here is just to route the
    dedup module's below_floor_action signal into the writer cache)."""
    sg_path = PROJECT_ROOT / "src" / "generation" / "script_generator.py"
    src = sg_path.read_text()
    drop_check_pos = src.index('if result.below_floor_action == "dropped":')
    skipped_branch_pos = src.index(
        "elif not result.skipped and result.deduped_transcript:"
    )
    assert drop_check_pos < skipped_branch_pos, (
        "the below-floor drop check must come first so it isn't masked by "
        "the not-skipped branch"
    )
