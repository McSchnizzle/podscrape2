"""Two v4.01 fixes in the pre-generation dedup pass.

1. PROVENANCE. The pass is documented as a removal pass but implemented as
   free-form generation with up to 200k chars of prior digest scripts in
   context. On 2026-08-08 the digest reproduced a share-price figure present
   in no source transcript for that day and only in the previous day's script,
   and this pass was the only component that saw both. Output sentences must
   now come from the input; a chunk that invents text is discarded in favor of
   the raw chunk.

2. SIBLING CONTEXT. `dedup_episode_batch` documents comparing each episode
   against the already-deduped siblings in its batch. It appended them to the
   end of `prior_content` while the truncation kept the first 200k -- and
   prior digest scripts alone exceed 200k, so the siblings were cut off every
   single call. Every recent run logged exactly "200,000 chars prior context"
   for all nine episodes. The comparison never ran.
"""
from __future__ import annotations

import pytest

from src.generation import transcript_dedup as td


# ---------------------------------------------------------------------------
# 1. Provenance
# ---------------------------------------------------------------------------


def test_invented_sentences_accepts_faithful_removal():
    source = (
        "The company announced a new chip today at its developer event. "
        "Analysts expected the announcement for several months beforehand. "
        "The stock closed flat despite the news coverage."
    )
    kept = "The company announced a new chip today at its developer event."
    assert td._invented_sentences(kept, source) == []


def test_invented_sentences_flags_text_not_in_source():
    source = "The company announced a new chip today at its developer event."
    fabricated = "Shares of the company fell four percent on the announcement."
    assert td._invented_sentences(fabricated, source)


def test_invented_sentences_tolerates_punctuation_and_case_repair():
    """Dedup may tidy transcription artifacts; it may not add words."""
    source = "the company announced a new chip today at its developer event"
    tidied = "The company announced a new chip today at its developer event."
    assert td._invented_sentences(tidied, source) == []


def test_invented_sentences_ignores_short_fragments():
    """Sentence splitting on real transcripts produces plenty of shards."""
    source = "A long sentence with plenty of words in it for matching purposes."
    assert td._invented_sentences("Right. Yeah. Okay so.", source) == []


def test_dedup_keeps_raw_chunk_when_output_is_invented(monkeypatch):
    """End to end: a hallucinating dedup call must not reach the writer."""
    transcript = (
        "The company announced a new chip today at its developer event. "
        "Analysts had expected this announcement for several months beforehand. "
    ) * 30

    monkeypatch.setattr(
        td,
        "_call_claude_p",
        lambda *a, **k: "Google shares slid four percent after the surprise executive departure.",
    )
    monkeypatch.setattr(td, "split_transcript_into_chunks", lambda t, n: [t])

    result = td.dedup_transcript(
        transcript=transcript,
        episode_title="Invented output",
        episode_id=1,
        prior_content="unrelated prior digest text",
    )
    # The fabricated sentence must not survive; the raw chunk stands in.
    assert "four percent" not in result.deduped_transcript
    assert result.deduped_transcript == transcript


def test_dedup_accepts_faithful_output(monkeypatch):
    """The check must not reject legitimate removal, or dedup stops working."""
    sentence_a = "The company announced a new chip today at its developer event. "
    sentence_b = "Analysts had expected this announcement for several months beforehand. "
    transcript = (sentence_a + sentence_b) * 30

    monkeypatch.setattr(td, "_call_claude_p", lambda *a, **k: sentence_a * 30)
    monkeypatch.setattr(td, "split_transcript_into_chunks", lambda t, n: [t])

    result = td.dedup_transcript(
        transcript=transcript,
        episode_title="Faithful removal",
        episode_id=2,
        prior_content="unrelated prior digest text",
    )
    assert result.deduped_chars < len(transcript)
    assert "Analysts had expected" not in result.deduped_transcript


# ---------------------------------------------------------------------------
# 2. Sibling context survives truncation
# ---------------------------------------------------------------------------


def test_sibling_content_survives_oversized_prior_digests(monkeypatch):
    """The exact live bug: prior digests alone blow the budget."""
    seen = {}

    def capture(prompt, timeout=300):
        seen["prompt"] = prompt
        return "The unique marker sentence appears here in the cleaned output."

    monkeypatch.setattr(td, "_call_claude_p", capture)
    monkeypatch.setattr(td, "split_transcript_into_chunks", lambda t, n: [t])

    huge_prior = "PRIOR DIGEST FILLER. " * 20_000  # ~400k chars, over the cap
    assert len(huge_prior) > td.MAX_PRIOR_DIGEST_CHARS

    td.dedup_transcript(
        transcript="The unique marker sentence appears here in the cleaned output. " * 20,
        episode_title="Sibling test",
        episode_id=3,
        prior_content=huge_prior,
        sibling_content="--- ALREADY SELECTED: Sibling Episode ---\nSIBLING_MARKER_TEXT\n",
    )

    assert "SIBLING_MARKER_TEXT" in seen["prompt"], (
        "sibling context was truncated away -- the batch's own dedup is inert"
    )


def test_prior_digest_content_is_still_capped(monkeypatch):
    seen = {}

    def capture(prompt, timeout=300):
        seen["prompt"] = prompt
        return "The unique marker sentence appears here in the cleaned output."

    monkeypatch.setattr(td, "_call_claude_p", capture)
    monkeypatch.setattr(td, "split_transcript_into_chunks", lambda t, n: [t])

    huge_prior = "PRIOR DIGEST FILLER. " * 20_000
    td.dedup_transcript(
        transcript="The unique marker sentence appears here in the cleaned output. " * 20,
        episode_title="Cap test",
        episode_id=4,
        prior_content=huge_prior,
    )
    # Prompt carries the capped prior content plus the transcript and rules,
    # nowhere near the full 400k.
    assert len(seen["prompt"]) < td.MAX_PRIOR_DIGEST_CHARS + 100_000


def test_batch_accumulates_siblings_separately(monkeypatch):
    """dedup_episode_batch must pass siblings via the dedicated argument."""
    calls = []

    def fake_dedup(**kwargs):
        calls.append(kwargs)
        return td.TranscriptDedupResult(
            episode_id=kwargs["episode_id"],
            episode_title=kwargs["episode_title"],
            original_chars=len(kwargs["transcript"]),
            deduped_chars=len(kwargs["transcript"]),
            deduped_transcript=kwargs["transcript"],
        )

    monkeypatch.setattr(td, "dedup_transcript", fake_dedup)
    monkeypatch.setattr(td, "detect_evergreen_topics", lambda scripts: [])

    class _Ep:
        def __init__(self, i):
            self.id = i
            self.title = f"Episode {i}"
            self.transcript_content = f"UNIQUE_BODY_{i} " * 100

    td.dedup_episode_batch([_Ep(1), _Ep(2)], prior_digest_scripts=["a prior digest"])

    assert calls[0]["sibling_content"] == ""
    assert "UNIQUE_BODY_1" in calls[1]["sibling_content"], (
        "second episode was not compared against the first"
    )
    # Prior digest content must stay separate from sibling content.
    assert "UNIQUE_BODY_1" not in calls[1]["prior_content"]


# ---------------------------------------------------------------------------
# Sentence-level stripping (refinement measured against the Aug 8 pool)
# ---------------------------------------------------------------------------


def test_strip_invented_removes_only_the_offending_sentence():
    """Whole-chunk rejection cost most of the dedup benefit. Measured on the
    2026-08-08 pool it fired on 11 chunks and pushed episode 794 from 54%
    retained back to 82% -- nearly always over one or two stray sentences."""
    # Realistic proportions: a 30k chunk is hundreds of sentences, so one or
    # two strays are a couple of percent, not a third. A three-sentence output
    # would (correctly) exceed MAX_INVENTED_FRACTION and be discarded whole --
    # an output that short from a real chunk is itself a red flag.
    source = (
        "The company announced a new chip today at its developer event. "
        "Analysts had expected this announcement for several months beforehand. "
        "The stock closed flat despite the wide news coverage that followed. "
    ) * 20
    output = (
        "The company announced a new chip today at its developer event. "
        "Analysts had expected this announcement for several months beforehand. "
        "The stock closed flat despite the wide news coverage that followed. "
    ) * 20 + "This transcript covers chips and earnings, none of which is new."
    cleaned, removed, fraction = td.strip_invented(output, source)
    assert len(removed) == 1
    assert "This transcript covers" in removed[0]
    assert "announced a new chip" in cleaned
    assert "stock closed flat" in cleaned
    assert 0 < fraction < td.MAX_INVENTED_FRACTION


def test_heavy_rewrite_falls_back_to_the_raw_chunk(monkeypatch):
    """Past MAX_INVENTED_FRACTION the model rewrote rather than removed, and
    stripping would leave incoherent text."""
    transcript = "The company announced a new chip today at its developer event. " * 40
    monkeypatch.setattr(
        td, "_call_claude_p",
        lambda *a, **k: "Google shares slid four percent after the surprise departure. " * 10,
    )
    monkeypatch.setattr(td, "split_transcript_into_chunks", lambda t, n: [t])

    result = td.dedup_transcript(
        transcript=transcript, episode_title="Heavy rewrite", episode_id=9,
        prior_content="unrelated prior digest text",
    )
    assert result.deduped_transcript == transcript
    assert "four percent" not in result.deduped_transcript


def test_light_contamination_is_stripped_not_discarded(monkeypatch):
    """The real 2026-08-08 shape: mostly faithful output with one line lifted
    from a prior digest script."""
    keep = "The company announced a new chip today at its developer event. "
    transcript = keep * 40
    leaked = "SPEAKER_1: Natasha here, and Malcolm, and here is the number I cannot get past. "
    monkeypatch.setattr(td, "_call_claude_p", lambda *a, **k: (keep * 20) + leaked)
    monkeypatch.setattr(td, "split_transcript_into_chunks", lambda t, n: [t])

    result = td.dedup_transcript(
        transcript=transcript, episode_title="Leaked line", episode_id=10,
        prior_content="prior digest containing that line",
    )
    assert "Natasha here" not in result.deduped_transcript, "prior-digest text survived"
    assert "announced a new chip" in result.deduped_transcript, "dedup work was thrown away"
    assert result.deduped_chars < len(transcript)
