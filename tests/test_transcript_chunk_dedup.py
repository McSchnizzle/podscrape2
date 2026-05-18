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
    """Transcript <= 30k chars must result in exactly 1 claude -p call."""
    _patch_claude_healthy(monkeypatch)

    transcript = ("This is a sentence about something interesting. " * 500)  # ~24k
    assert len(transcript) < MAX_CHUNK_CHARS

    call_count = {"n": 0}

    def fake_call(prompt, timeout=300):
        call_count["n"] += 1
        return "CLEANED_OUTPUT"

    monkeypatch.setattr(transcript_dedup, "_call_claude_p", fake_call)

    result = dedup_transcript(
        transcript=transcript,
        episode_title="Short ep",
        episode_id=1,
        prior_content="some prior content",
    )

    assert call_count["n"] == 1
    assert result.skipped is False
    assert result.deduped_transcript == "CLEANED_OUTPUT"
    assert result.original_chars == len(transcript)
    assert result.deduped_chars == len("CLEANED_OUTPUT")


def test_dedup_transcript_chunks_when_over_30k(monkeypatch):
    """Transcript > 30k chars triggers >=2 claude -p calls, results ordered."""
    _patch_claude_healthy(monkeypatch)

    transcript = FIXTURE_PATH.read_text()
    assert len(transcript) > MAX_CHUNK_CHARS

    calls = []

    def fake_call(prompt, timeout=300):
        idx = len(calls) + 1
        calls.append(prompt)
        return f"[CLEAN-{idx}]"

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
    """`[NO_NEW_CONTENT]` from one chunk drops that chunk only, not others."""
    _patch_claude_healthy(monkeypatch)

    transcript = FIXTURE_PATH.read_text()

    calls = {"n": 0}

    def fake_call(prompt, timeout=300):
        calls["n"] += 1
        if calls["n"] == 1:
            return "[NO_NEW_CONTENT]"
        return f"chunk{calls['n']} novel content"

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
