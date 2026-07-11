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
    kept = "This is genuinely novel analysis not covered anywhere else. " * 40
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
        if "Sibling content A." in prompt or "Sibling content B." in prompt:
            return "Sibling novel framing not covered elsewhere. " * 50
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
    ep_kept = _ThesisEpisode(1, "Kept episode", "Novel content. " * 300)
    ep_restored = _ThesisEpisode(2, "Restored episode", _ep19_style_original() + " RESTORE_MARKER")
    ep_dropped = _ThesisEpisode(3, "Dropped episode", _ep19_style_original() + " DROP_MARKER")

    def fake_call(prompt, timeout=300):
        if "Novel content." in prompt:
            return "Genuinely novel material not covered anywhere else. " * 30
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
    assert dropped_count == empty_count  # every below-floor drop IS a zero-char result
    assert restored_count == 1

    summary_lines = [rec.message for rec in caplog.records if "batch complete" in rec.message]
    assert summary_lines, "expected a 'Pre-gen dedup batch complete' summary log line"
    assert "1 fully redundant/dropped" in summary_lines[-1]
    assert "1 restored" in summary_lines[-1]


# ---------------------------------------------------------------------------
# script_generator.py cleanup wiring (kanban #2861)
# ---------------------------------------------------------------------------


def test_script_generator_no_longer_falsely_claims_key_insights_present():
    """The dialogue/narrative writer prompts must not tell the model 'the
    key insights are present' regardless of transcript length -- that was
    a false claim once dedup could hand it a below-floor stub. Now that the
    safety net guarantees a floor, the prompt should say so truthfully."""
    sg_path = PROJECT_ROOT / "src" / "generation" / "script_generator.py"
    src = sg_path.read_text()
    assert "the key insights are present" not in src
    assert "content was truncated for length" not in src
    # The truthful replacement should still be present (dialogue + narrative).
    assert src.count("self-supporting") >= 2


def test_script_generator_marks_dropped_episodes_as_digested():
    """Episodes the safety net drops for zero novel content must still be
    marked digested (covered by siblings) so they don't resurface tomorrow
    only to be re-deduped to nothing again."""
    sg_path = PROJECT_ROOT / "src" / "generation" / "script_generator.py"
    src = sg_path.read_text()
    assert "dropped_episode_ids" in src
    assert "mark_episode_as_digested(dropped_ep)" in src
