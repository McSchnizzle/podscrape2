"""
Pre-generation transcript deduplication (v3.33+).

Strips content from episode transcripts that was already covered in prior
digest scripts BEFORE the script generator sees them. This is fundamentally
different from the post-generation dedup pass:

- Post-gen dedup: generates a full script, then tries to remove repeated
  content. Fails because the LLM already fixated on familiar topics and
  ignored diverse material.

- Pre-gen dedup: strips each transcript of content that overlaps with prior
  digests, so the LLM only sees novel material. Produces better scripts
  because the input itself is de-duplicated.

The dedup is sequential: episode A is compared against prior digests 1-8.
Episode B is compared against digests 1-8 PLUS the deduped version of A.
This prevents two episodes that cover the same new story from both sending
that story to the generator.

Uses claude -p (free via Max subscription) for semantic dedup — simple
string matching would miss paraphrased content.
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


# kanban #430: split transcripts > MAX_CHUNK_CHARS into sentence-aligned
# chunks so each chunk fits comfortably in a single claude -p round-trip.
# 30,000 chars ~= 7,500 tokens, well under the model's context budget and
# leaves plenty of room for prior_content + the system prompt.
MAX_CHUNK_CHARS = 30_000

# kanban #2861: safety-net floor. Dedup must never hand the script writer a
# below-floor stub -- a fragment so thin the writer can only reference it as
# "we don't have the detail." If a NON-empty dedup result falls below this
# many chars (or below MIN_RETENTION_PCT of the original), we restore a
# bounded excerpt of the ORIGINAL transcript instead of the over-stripped
# output. A genuinely empty result (all chunks [NO_NEW_CONTENT]) is not a
# stub -- it means the episode really has nothing new, so it is dropped
# from the writer input instead of restored. See dedup_transcript().
MIN_DEDUPED_CHARS = 500
MIN_RETENTION_PCT = 0.15

# Cap for the restored excerpt (kanban #2861 safety net). Bounded so a
# restore doesn't reintroduce full-transcript duplication against sibling
# episodes -- just enough for the episode's own thesis + supporting
# reasoning to stand on its own.
RESTORE_EXCERPT_CAP_CHARS = 3_000

# Sentence-end pattern: ., !, ? followed by whitespace. Catches the vast
# majority of natural break points in podcast transcripts (which are
# typically punctuated prose from whisper-style transcription). The
# trailing whitespace is what we split AFTER so the chunk ends cleanly
# on punctuation and the next chunk starts on the next sentence.
_SENTENCE_END_RE = re.compile(r"[.!?](?:\s|$)")


def split_transcript_into_chunks(
    text: str,
    max_chunk_chars: int = MAX_CHUNK_CHARS,
) -> List[str]:
    """Split a transcript into <=max_chunk_chars chunks at sentence boundaries.

    Properties (kanban #430 AC1):
    - Pure function. No I/O, no side effects.
    - Returns ``[text]`` when ``len(text) <= max_chunk_chars`` (including the
      empty-string case, which yields ``[""]``).
    - Lossless: ``"".join(split_transcript_into_chunks(t)) == t`` for ANY
      input.
    - Splits at sentence boundaries (``.``, ``!``, ``?`` followed by
      whitespace or end-of-string) whenever possible.
    - Falls back to a hard cut at ``max_chunk_chars`` when no sentence
      boundary exists in the window -- prevents one pathological run-on
      sentence from producing a single giant chunk.

    Args:
        text: The transcript to split.
        max_chunk_chars: Maximum chars per chunk. Defaults to
            ``MAX_CHUNK_CHARS`` (30,000).

    Returns:
        List of chunk strings whose concatenation equals ``text``.
    """
    if max_chunk_chars <= 0:
        raise ValueError(f"max_chunk_chars must be positive, got {max_chunk_chars}")

    n = len(text)
    if n <= max_chunk_chars:
        return [text]

    chunks: List[str] = []
    start = 0
    while start < n:
        # If the remainder fits in one chunk, emit it and stop.
        if n - start <= max_chunk_chars:
            chunks.append(text[start:])
            break

        # Find the last sentence boundary in the window [start, start+max).
        window_end = start + max_chunk_chars
        window = text[start:window_end]
        last_boundary_end = -1
        for m in _SENTENCE_END_RE.finditer(window):
            # m.end() is just past the trailing whitespace/end-of-window.
            # We want to split AFTER that whitespace so the chunk ends on
            # the punctuation+space and the next chunk starts clean.
            last_boundary_end = m.end()

        if last_boundary_end <= 0:
            # No sentence boundary in the window -- hard split at the
            # window edge. Still lossless.
            split_at = window_end
        else:
            split_at = start + last_boundary_end

        chunks.append(text[start:split_at])
        start = split_at

    return chunks


@dataclass
class TranscriptDedupResult:
    """Result of deduping a single transcript."""
    episode_id: int
    episode_title: str
    original_chars: int
    deduped_chars: int
    deduped_transcript: str
    skipped: bool = False
    skip_reason: Optional[str] = None
    # kanban #2861 safety net: None (no action), "dropped" (deduped_chars==0,
    # genuinely no new content -- excluded from writer input), or "restored"
    # (dedup output fell below the floor, so deduped_transcript was replaced
    # with a bounded excerpt of the ORIGINAL transcript).
    below_floor_action: Optional[str] = None

    @property
    def reduction_pct(self) -> float:
        if self.original_chars == 0:
            return 0.0
        return 1.0 - (self.deduped_chars / self.original_chars)


_DEDUP_SYSTEM_PROMPT = """\
You are a transcript editor. Your job is to remove content from a podcast \
transcript that was ALREADY REPORTED in prior digest scripts.

You will receive:
1. PRIOR CONTENT: Snippets from recent digest scripts that our audience \
already heard.
2. TRANSCRIPT: A new episode transcript to clean.

Your task: Return a CLEANED version of the transcript with the following removed:
- Paragraphs or sentences that restate facts, statistics, or claims already \
present in the PRIOR CONTENT, when those facts are pure background recitation \
and are NOT being used to build this episode's own point.
- Background explanations for stories already covered (e.g., "Project Glasswing \
is a coalition of...").
- Repeated benchmark numbers, partner lists, or other specific data points \
that appear in the PRIOR CONTENT — UNLESS this episode is using them as \
evidence for its own distinct verdict or conclusion (see CRITICAL rule below).

CRITICAL — NEVER reduce an episode to an unsupported claim:
- If the transcript states this episode's own thesis, evaluation, or verdict \
on a topic — especially a take that DIFFERS from or CONTRADICTS how prior \
digests framed the same topic (e.g., a negative review of something prior \
episodes praised) — you MUST keep that verdict AND the minimum supporting \
facts, reasoning, or evidence it depends on, even when those specific facts \
(benchmark numbers, data points) also appear in PRIOR CONTENT.
- A distinctive or contrarian opinion is high-value content precisely because \
it disagrees. Stripping the evidence out from under it leaves a bare assertion \
the audience can't evaluate — that is worse than leaving in a duplicate fact.
- Test before removing a fact: "if I strip this, does the episode's own \
conclusion still make sense standing on its own?" If not, keep it.
- Only strip evidence that is pure duplicate recitation NOT doing any work \
for this episode's own argument.

KEEP:
- The episode's central thesis/evaluation/verdict and its supporting reasoning \
(per the CRITICAL rule above), even when built on facts covered elsewhere.
- Any genuinely NEW information, angles, reactions, or data not in PRIOR CONTENT.
- A new source's perspective on a familiar story (different host/guest opinion).
- New consequences, reversals, or developments of a known story.
- Any topic or content NOT related to the prior digests at all.
- The transcript's natural structure — do not restructure or summarize. \
Just remove the redundant parts and leave the rest intact.

If almost everything in the transcript is redundant, return only the novel \
parts, even if that's just a few sentences. If the transcript has NOTHING \
new — no distinct thesis, no novel angle, nothing beyond a restatement of \
what prior digests already said — return the single line: [NO_NEW_CONTENT]

Output ONLY the cleaned transcript. No commentary, no headers, no notes.
"""


def _call_claude_p(prompt: str, timeout: int = 300) -> str:
    """Run claude -p and return stdout."""
    claude_path = os.path.expanduser("~/.local/bin/claude")
    if not os.path.exists(claude_path):
        claude_path = "claude"

    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    env.pop("ANTHROPIC_API_KEY", None)

    result = subprocess.run(
        [
            claude_path, "-p",
            "--model", "sonnet",
            "--effort", "low",
            "--tools", "",
            "--no-session-persistence",
            "-",
        ],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"claude -p failed (exit {result.returncode}): {result.stderr[:300]}"
        )
    return result.stdout.strip()


def _build_dedup_prompt(
    transcript: str,
    prior_content: str,
    episode_title: str,
    evergreen_topics: Optional[List[str]] = None,
) -> str:
    """Build the full prompt for transcript dedup."""
    evergreen_section = ""
    if evergreen_topics:
        topics_list = "\n".join(f"- {t}" for t in evergreen_topics)
        evergreen_section = (
            f"\n## SATURATED TOPICS (aggressive stripping required)\n\n"
            f"These stories have been covered in 3+ recent digests. Our audience "
            f"is thoroughly familiar with the background:\n\n{topics_list}\n\n"
            f"**For SATURATED topics, strip MORE aggressively:**\n"
            f"- Remove ALL background, exposition, and context — listeners know it\n"
            f"- Remove ALL re-introductions of entities, partner lists, benchmark "
            f"numbers, quoted sources that were already named\n"
            f"- Keep ONLY: genuinely new developments from today (new quote from a "
            f"new source, new data point, new reaction, new consequence, new reversal)\n"
            f"- If a paragraph is explaining what a saturated topic IS, rather than "
            f"what's new about it, REMOVE the paragraph entirely\n"
            f"- A mention like 'the Mythos story we've been tracking' is fine — "
            f"re-explaining what Mythos is is NOT\n\n"
            f"**This aggressive stripping is SUBORDINATE to the CRITICAL rule "
            f"above:** even on a saturated topic, never strip the specific "
            f"evidence this episode needs to support its OWN distinct verdict "
            f"or conclusion. 'Familiar background' means re-explained context "
            f"and re-listed facts nobody is using to argue anything new — it "
            f"does NOT mean the facts this episode is standing its argument on.\n\n"
        )

    return (
        f"{_DEDUP_SYSTEM_PROMPT}\n\n"
        f"## PRIOR CONTENT (what our audience already knows)\n\n"
        f"{prior_content}\n"
        f"{evergreen_section}"
        f"---\n\n"
        f"## TRANSCRIPT TO CLEAN: \"{episode_title}\"\n\n"
        f"{transcript}\n\n"
        f"---\n\n"
        f"Return ONLY the cleaned transcript with redundant content removed."
    )


_EVERGREEN_DETECTION_PROMPT = """\
You are analyzing recent podcast digest scripts to identify SATURATED TOPICS —
stories that have been covered in 3 or more of the recent digests and whose
background is now thoroughly familiar to the audience.

You will receive the last several digest scripts. Return a list of saturated
topics, one per line, in this format:

- Topic name: one-line description of the core story/entity

Rules for what counts as SATURATED:
- The topic appears with meaningful coverage (not just a passing mention) in 3+ \
digests
- The background, key players, and main facts have been explained before
- New episodes should focus on fresh angles, not re-establish the story

DO NOT include:
- Topics covered in only 1-2 digests (they're not saturated yet)
- Generic themes like "AI safety" or "open source" (too broad)
- Ongoing trends without a specific story anchor
- Topics that only appeared in one digest with tangential mentions

Format your response as a plain list. If no topics qualify, return the single \
line: [NO_SATURATED_TOPICS]

Examples of GOOD saturated topics:
- Anthropic Claude Mythos: Unreleased frontier model with cybersecurity capabilities
- Project Glasswing: Anthropic's controlled-access program for Mythos with big tech partners
- Muse Spark launch: Meta's first model from Meta Super Intelligence Labs

Examples of things NOT to include:
- Too broad: "AI safety concerns"
- Not saturated: "Google's new Gemini feature" (only appeared once)
- Generic: "Open-weight models" (a category, not a story)

Output ONLY the bullet list, no preamble or explanation.
"""


def detect_evergreen_topics(
    prior_digest_scripts: List[str],
    timeout: int = 240,
) -> List[str]:
    """Identify stories that have been covered in 3+ recent digests.

    These "saturated" topics get stricter dedup handling — background and
    exposition must be stripped even if the specific wording is new.

    Args:
        prior_digest_scripts: Recent digest scripts, most-recent-first.
        timeout: claude -p timeout.

    Returns:
        List of topic descriptions (possibly empty).
    """
    if len(prior_digest_scripts) < 3:
        logger.info("Evergreen detection: fewer than 3 prior digests, skipping")
        return []

    try:
        from src.utils.claude_p_health import is_claude_p_healthy
        if not is_claude_p_healthy():
            logger.info("Evergreen detection: claude -p unhealthy, skipping")
            return []
    except Exception:
        pass

    # Use up to 5 most recent digests, trimmed to fit under ~80k chars total
    selected = prior_digest_scripts[:5]
    lines = []
    for i, script in enumerate(selected, start=1):
        # Send full digest scripts -- no truncation (Paul directive 2026-05-07)
        lines.append(f"--- DIGEST {i} (most recent first) ---\n{script}\n")
    digests_text = "\n".join(lines)

    prompt = (
        f"{_EVERGREEN_DETECTION_PROMPT}\n\n"
        f"## RECENT DIGESTS\n\n"
        f"{digests_text}\n\n"
        f"---\n\n"
        f"Return the bullet list of saturated topics now."
    )

    try:
        logger.info(
            f"Evergreen detection: scanning {len(selected)} digests "
            f"({len(digests_text):,} chars)"
        )
        response = _call_claude_p(prompt, timeout=timeout)
    except subprocess.TimeoutExpired:
        logger.warning("Evergreen detection timed out, continuing without it")
        return []
    except Exception as e:
        logger.warning(f"Evergreen detection failed: {e}, continuing without it")
        return []

    if "[NO_SATURATED_TOPICS]" in response:
        logger.info("Evergreen detection: no saturated topics found")
        return []

    # Parse bullet list
    topics = []
    for line in response.split("\n"):
        line = line.strip()
        if line.startswith("- ") or line.startswith("* "):
            topics.append(line[2:].strip())
        elif line.startswith("• "):
            topics.append(line[2:].strip())

    logger.info(f"Evergreen detection: found {len(topics)} saturated topics")
    for t in topics:
        logger.info(f"  - {t}")
    return topics


def _restore_bounded_excerpt(
    original: str,
    cap: int = RESTORE_EXCERPT_CAP_CHARS,
) -> str:
    """Return a sentence-trimmed excerpt of ``original``, capped at ``cap`` chars.

    kanban #2861 safety net: when dedup over-strips a distinctive episode
    below the floor, we fall back to a bounded slice of the ORIGINAL
    transcript (not the over-stripped output) so the writer gets coherent,
    self-supporting content instead of a fragment. Reuses the same
    sentence-boundary logic as ``split_transcript_into_chunks`` so the
    excerpt ends cleanly rather than mid-sentence.
    """
    if len(original) <= cap:
        return original

    window = original[:cap]
    last_boundary_end = -1
    for m in _SENTENCE_END_RE.finditer(window):
        last_boundary_end = m.end()

    return original[:last_boundary_end] if last_boundary_end > 0 else window


def dedup_transcript(
    transcript: str,
    episode_title: str,
    episode_id: int,
    prior_content: str,
    timeout: int = 300,
    evergreen_topics: Optional[List[str]] = None,
) -> TranscriptDedupResult:
    """Dedup a single transcript against prior content.

    Args:
        transcript: The episode transcript to clean.
        episode_title: Title for logging.
        episode_id: Episode ID for tracking.
        prior_content: Combined text of prior digests + previously deduped
            transcripts in this batch.
        timeout: claude -p timeout in seconds.
        evergreen_topics: Optional list of saturated topics that should be
            stripped more aggressively.

    Returns:
        TranscriptDedupResult with the cleaned transcript.
    """
    original_chars = len(transcript)

    if original_chars < 500:
        return TranscriptDedupResult(
            episode_id=episode_id,
            episode_title=episode_title,
            original_chars=original_chars,
            deduped_chars=original_chars,
            deduped_transcript=transcript,
            skipped=True,
            skip_reason="transcript too short",
        )

    # Check claude -p health
    try:
        from src.utils.claude_p_health import is_claude_p_healthy
        if not is_claude_p_healthy():
            return TranscriptDedupResult(
                episode_id=episode_id,
                episode_title=episode_title,
                original_chars=original_chars,
                deduped_chars=original_chars,
                deduped_transcript=transcript,
                skipped=True,
                skip_reason="claude -p unhealthy",
            )
    except Exception:
        pass

    # Truncate prior content if massive (keep most recent, which is most relevant)
    # Prior content is ordered most-recent-first, so [:max_prior] keeps the
    # newest digests. 200k chars (~50k tokens) covers the last 6-7 digests
    # (~1 week), enough to catch entities introduced earlier in the news cycle.
    max_prior = 200_000
    if len(prior_content) > max_prior:
        prior_content = prior_content[:max_prior]

    # Send the full transcript to dedup. The deduped result replaces
    # ep.transcript_content in the script generator, so truncating here
    # silently drops content the script writer never sees. Bug: 2026-05-06
    # ep 2748 (31k chars). Timeout is handled by timeout_per_episode=300s.
    # max_transcript removed -- send full transcript

    # kanban #430: chunk transcripts > MAX_CHUNK_CHARS so each round-trip
    # to claude -p stays well inside context/output budgets. Each chunk
    # is deduped against the SAME prior_content (so the "already covered"
    # signal is identical for every chunk) and the cleaned chunks are
    # concatenated in order. Lossless on the input side; preserves
    # order on the output side.
    chunks = split_transcript_into_chunks(transcript, MAX_CHUNK_CHARS)
    is_chunked = len(chunks) > 1

    if is_chunked:
        logger.info(
            f"Pre-gen dedup: '{episode_title[:50]}' "
            f"({original_chars:,} chars transcript, "
            f"{len(prior_content):,} chars prior context) "
            f"-> split into {len(chunks)} chunks"
        )
    else:
        logger.info(
            f"Pre-gen dedup: '{episode_title[:50]}' "
            f"({original_chars:,} chars transcript, "
            f"{len(prior_content):,} chars prior context)"
        )

    cleaned_parts: List[str] = []
    for i, chunk in enumerate(chunks, start=1):
        chunk_title = (
            f"{episode_title} [part {i}/{len(chunks)}]"
            if is_chunked
            else episode_title
        )
        prompt = _build_dedup_prompt(
            chunk,
            prior_content,
            chunk_title,
            evergreen_topics=evergreen_topics,
        )
        try:
            cleaned_chunk = _call_claude_p(prompt, timeout=timeout)
        except subprocess.TimeoutExpired:
            # Fail loudly: ANY chunk failure aborts the whole dedup and
            # surfaces a skipped result. We do NOT silently emit a
            # partial dedup (kanban #430 AC3).
            reason = (
                f"chunk {i}/{len(chunks)} timeout"
                if is_chunked
                else "timeout"
            )
            logger.warning(
                f"Pre-gen dedup timed out for '{episode_title[:50]}' "
                f"({reason}), using original"
            )
            return TranscriptDedupResult(
                episode_id=episode_id,
                episode_title=episode_title,
                original_chars=original_chars,
                deduped_chars=original_chars,
                deduped_transcript=transcript,
                skipped=True,
                skip_reason=reason,
            )
        except Exception as e:
            reason = (
                f"chunk {i}/{len(chunks)} failed: {e}"
                if is_chunked
                else str(e)
            )
            logger.warning(
                f"Pre-gen dedup failed for '{episode_title[:50]}': {reason}"
            )
            return TranscriptDedupResult(
                episode_id=episode_id,
                episode_title=episode_title,
                original_chars=original_chars,
                deduped_chars=original_chars,
                deduped_transcript=transcript,
                skipped=True,
                skip_reason=reason,
            )

        # Handle the [NO_NEW_CONTENT] sentinel per-chunk: that chunk
        # contributes nothing to the cleaned output but processing continues.
        if "[NO_NEW_CONTENT]" in cleaned_chunk:
            if is_chunked:
                logger.info(
                    f"Pre-gen dedup: '{episode_title[:50]}' chunk "
                    f"{i}/{len(chunks)} has no new content"
                )
            cleaned_parts.append("")
        else:
            cleaned_parts.append(cleaned_chunk)

    # Reassemble. Use "\n\n" between non-empty chunks so the script
    # generator sees a natural paragraph break at chunk seams; drop
    # empty parts so [NO_NEW_CONTENT] chunks don't introduce blank gaps.
    non_empty = [p for p in cleaned_parts if p]
    cleaned = "\n\n".join(non_empty) if is_chunked else (cleaned_parts[0] if cleaned_parts else "")

    if not cleaned and is_chunked:
        logger.info(
            f"Pre-gen dedup: '{episode_title[:50]}' has no new content "
            f"(all {len(chunks)} chunks empty)"
        )

    deduped_chars = len(cleaned)
    retained_pct = (deduped_chars / original_chars) if original_chars else 0.0
    if original_chars > 0:
        logger.info(
            f"Pre-gen dedup: '{episode_title[:50]}' "
            f"{original_chars:,} -> {deduped_chars:,} chars "
            f"({retained_pct:.0%} retained)"
        )

    # kanban #2861 safety net: dedup must never hand the writer a
    # below-floor stub it can only reference as "we don't have the detail."
    below_floor_action: Optional[str] = None
    if deduped_chars == 0:
        # Genuinely nothing new (every chunk returned [NO_NEW_CONTENT], or
        # the model emptied the transcript outright). This is NOT a stub --
        # it's a real "fully redundant" result, so it stays empty and the
        # caller drops the episode from writer input.
        below_floor_action = "dropped"
        logger.info(
            f"Pre-gen dedup safety net: '{episode_title[:50]}' fully "
            f"redundant (0% retained) -- dropping from writer input"
        )
    elif deduped_chars < MIN_DEDUPED_CHARS or retained_pct < MIN_RETENTION_PCT:
        # Dedup found SOME novel content but stripped too much of its
        # support to stand alone -- restore a bounded excerpt of the
        # ORIGINAL transcript instead of handing the writer a fragment.
        restored = _restore_bounded_excerpt(transcript)
        logger.warning(
            f"Pre-gen dedup safety net: '{episode_title[:50]}' over-stripped "
            f"to {deduped_chars:,} chars ({retained_pct:.0%} retained, below "
            f"floor of {MIN_DEDUPED_CHARS} chars / {MIN_RETENTION_PCT:.0%}) "
            f"-- restoring {len(restored):,}-char original excerpt"
        )
        cleaned = restored
        deduped_chars = len(cleaned)
        below_floor_action = "restored"

    return TranscriptDedupResult(
        episode_id=episode_id,
        episode_title=episode_title,
        original_chars=original_chars,
        deduped_chars=deduped_chars,
        deduped_transcript=cleaned,
        below_floor_action=below_floor_action,
    )


def dedup_episode_batch(
    episodes: List,
    prior_digest_scripts: List[str],
    timeout_per_episode: int = 300,
) -> Tuple[List[TranscriptDedupResult], str]:
    """Dedup a batch of episodes sequentially.

    Each episode is compared against:
    1. Prior digest scripts (what listeners already heard)
    2. Previously deduped transcripts in this batch (prevents two episodes
       from both submitting the same new story)

    Args:
        episodes: List of Episode objects with transcript_content.
        prior_digest_scripts: List of prior digest script strings.
        timeout_per_episode: claude -p timeout per episode.

    Returns:
        Tuple of (list of TranscriptDedupResult, combined_novel_content).
        combined_novel_content is the concatenation of all deduped transcripts,
        suitable for feeding to the script generator.
    """
    # Build the initial prior content from digest scripts
    prior_parts = []
    for i, script in enumerate(prior_digest_scripts):
        # Use full scripts — they're only 12-17k chars each
        prior_parts.append(f"--- PRIOR DIGEST {i+1} ---\n{script}\n")
    prior_content = "\n".join(prior_parts)

    # Detect saturated topics (covered in 3+ recent digests) so they get
    # stricter dedup handling — strip background, keep only what's new today.
    evergreen_topics = detect_evergreen_topics(prior_digest_scripts)

    results = []
    novel_transcripts = []

    for ep in episodes:
        transcript = ep.transcript_content or ""
        if not transcript.strip():
            results.append(TranscriptDedupResult(
                episode_id=ep.id,
                episode_title=ep.title,
                original_chars=0,
                deduped_chars=0,
                deduped_transcript="",
                skipped=True,
                skip_reason="empty transcript",
            ))
            continue

        result = dedup_transcript(
            transcript=transcript,
            episode_title=ep.title,
            episode_id=ep.id,
            prior_content=prior_content,
            timeout=timeout_per_episode,
            evergreen_topics=evergreen_topics,
        )
        results.append(result)

        # Add this episode's deduped content to the prior content
        # so the next episode is compared against it too
        if result.deduped_transcript and not result.skipped:
            novel_transcripts.append(
                f"--- EPISODE: {ep.title} ---\n{result.deduped_transcript}\n"
            )
            prior_content += f"\n--- ALREADY SELECTED: {ep.title} ---\n"
            prior_content += result.deduped_transcript + "\n"

    combined = "\n\n".join(novel_transcripts)

    # Summary logging
    total_original = sum(r.original_chars for r in results)
    total_deduped = sum(r.deduped_chars for r in results)
    skipped = sum(1 for r in results if r.skipped)
    # kanban #2861: "empty" already covers every below-floor DROP -- the
    # safety net only ever drops (vs. restores) when deduped_chars == 0.
    empty = sum(1 for r in results if r.deduped_chars == 0 and not r.skipped)
    restored = sum(1 for r in results if r.below_floor_action == "restored")

    logger.info(
        f"Pre-gen dedup batch complete: {len(results)} episodes, "
        f"{total_original:,} -> {total_deduped:,} chars "
        f"({total_deduped/total_original:.0%} retained), "
        f"{skipped} skipped, {empty} fully redundant/dropped, "
        f"{restored} restored (below-floor safety net)"
    )

    return results, combined
