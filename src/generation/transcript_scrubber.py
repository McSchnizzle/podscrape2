"""
Transcript scrubbing for dedup regeneration (v3.27+).

When the dedup expansion loop decides to regenerate a digest with MORE
episodes (because the post-dedup result was below target_chars_floor), we
first strip "already-saturated" content out of every episode transcript.
Otherwise the new draft would just re-introduce the same stale beats that
the dedup pass cut in iteration 1, and iteration 2 would cut them again —
wasted work, and often the model ends up regressing the cuts.

This module runs ONE `claude -p` call per episode per expansion iteration,
asking the model to remove sentences/paragraphs discussing a provided list
of saturated story topics while preserving everything else verbatim.

Not to be confused with ad filtering, which removes sponsorship segments.
"""
from __future__ import annotations

import copy
import logging
import os
import subprocess
from dataclasses import dataclass
from typing import List, Optional


def _claude_cli_model() -> str:
    """Alias for `claude -p --model`. Sourced from
    src/config/models.py::MODEL_ROLES so a model change is one edit,
    not eleven. Falls back to the previous literal if the import
    fails, so this can never break the pipeline."""
    try:
        from src.config.models import role
        return role("claude_cli")
    except Exception:
        return "sonnet"


logger = logging.getLogger(__name__)


class TranscriptScrubError(Exception):
    pass


@dataclass
class ScrubResult:
    chars_before: int
    chars_after: int
    skipped: bool = False
    skip_reason: Optional[str] = None

    @property
    def delta(self) -> int:
        return self.chars_after - self.chars_before


def _call_claude_p(system_prompt: str, user_prompt: str, timeout: int = 180) -> str:
    claude_path = os.path.expanduser("~/.local/bin/claude")
    if not os.path.exists(claude_path):
        claude_path = "claude"

    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    env.pop("ANTHROPIC_API_KEY", None)

    result = subprocess.run(
        [
            claude_path, "-p",
            "--model", _claude_cli_model(),
            "--effort", "medium",
            "--tools", "",
            "--no-session-persistence",
            "-",
        ],
        input=f"{system_prompt}\n\n{user_prompt}",
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    if result.returncode != 0:
        raise TranscriptScrubError(
            f"claude -p failed (exit {result.returncode}): {result.stderr[:400]}"
        )
    return result.stdout.strip()


_SCRUB_SYSTEM_PROMPT = """You are cleaning a podcast transcript before it is \
used as source material for a digest. Your job is to REMOVE all sentences and \
paragraphs that discuss the "saturated topics" listed below, while leaving \
every other part of the transcript EXACTLY as written.

Saturated topics are stories that our show has already covered multiple times \
in recent digests. We do NOT want the digest writer to re-encounter these \
topics in the source material and re-introduce them. Remove them cleanly so \
the downstream writer only sees content about other topics.

RULES:
- Remove any sentence, paragraph, or block of dialogue that is PRIMARILY \
about a saturated topic. "Primarily" means the topic is the subject of the \
sentence, not a passing mention.
- ONE-WORD mentions or background references ("OpenAI has raised money before, \
but this quarter...") should stay IF the surrounding sentence is about a \
different subject.
- Do NOT paraphrase, summarize, or rewrite the kept content. Keep it VERBATIM.
- Do NOT add transitional phrases like "[content removed]" or "...". Just \
stitch the remaining sentences together naturally.
- Do NOT add commentary, explanation, markdown, or notes.
- If the entire transcript is about saturated topics, return an empty string.
- If the transcript mentions NO saturated topics, return it unchanged verbatim.

OUTPUT: return ONLY the cleaned transcript text. Nothing else."""


def _build_scrub_user_prompt(transcript: str, saturated_topics: List[str]) -> str:
    topic_list = "\n".join(f"- {t}" for t in saturated_topics)
    return f"""SATURATED TOPICS to remove (these are already covered in recent digests):
{topic_list}

TRANSCRIPT to clean (return only the cleaned version, nothing else):

{transcript}
"""


def scrub_transcript(
    transcript: str,
    saturated_topics: List[str],
    *,
    timeout: int = 180,
) -> tuple[str, ScrubResult]:
    """Remove sentences discussing saturated topics from a single transcript.

    Returns (cleaned_transcript, ScrubResult). On any failure, returns the
    original transcript unchanged with skipped=True.
    """
    chars_before = len(transcript or "")

    if not transcript or chars_before < 500:
        return transcript, ScrubResult(
            chars_before=chars_before,
            chars_after=chars_before,
            skipped=True,
            skip_reason="transcript too short",
        )
    if not saturated_topics:
        return transcript, ScrubResult(
            chars_before=chars_before,
            chars_after=chars_before,
            skipped=True,
            skip_reason="no saturated topics",
        )

    # v3.29: skip if claude -p is broken on this host
    try:
        from src.utils.claude_p_health import is_claude_p_healthy
        if not is_claude_p_healthy():
            return transcript, ScrubResult(
                chars_before=chars_before,
                chars_after=chars_before,
                skipped=True,
                skip_reason="claude -p unhealthy (skipped via health probe)",
            )
    except Exception as e:
        logger.warning(f"Transcript scrub: health check failed ({e}); attempting anyway")

    try:
        cleaned = _call_claude_p(
            _SCRUB_SYSTEM_PROMPT,
            _build_scrub_user_prompt(transcript, saturated_topics),
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        logger.warning("Transcript scrub: claude -p timed out")
        # Note: we do NOT call mark_unhealthy() here. A prompt-specific
        # timeout is not the same as the CLI being broken.
        return transcript, ScrubResult(
            chars_before=chars_before,
            chars_after=chars_before,
            skipped=True,
            skip_reason="timeout",
        )
    except TranscriptScrubError as e:
        logger.warning(f"Transcript scrub: claude -p failed: {e}")
        return transcript, ScrubResult(
            chars_before=chars_before,
            chars_after=chars_before,
            skipped=True,
            skip_reason=str(e),
        )

    chars_after = len(cleaned)

    # Safety: don't accept catastrophic reductions (<10% of original) unless
    # the model genuinely decided the entire transcript was saturated.
    # Below 5%, assume the model misinterpreted and revert.
    if chars_after < chars_before * 0.05 and chars_after > 0:
        logger.warning(
            f"Transcript scrub: result implausibly short "
            f"({chars_after} vs {chars_before}); keeping original"
        )
        return transcript, ScrubResult(
            chars_before=chars_before,
            chars_after=chars_before,
            skipped=True,
            skip_reason="result too short",
        )

    # Don't accept lengthening — scrubbing can only remove.
    if chars_after > int(chars_before * 1.02):
        logger.warning(
            f"Transcript scrub: result longer than original "
            f"({chars_after} > {chars_before}); keeping original"
        )
        return transcript, ScrubResult(
            chars_before=chars_before,
            chars_after=chars_before,
            skipped=True,
            skip_reason="result longer than input",
        )

    logger.info(
        f"Transcript scrubbed: {chars_before} -> {chars_after} chars "
        f"({chars_after - chars_before:+d})"
    )
    return cleaned, ScrubResult(
        chars_before=chars_before,
        chars_after=chars_after,
        skipped=False,
    )


def scrub_episodes(
    episodes: list,
    saturated_topics: List[str],
    *,
    timeout: int = 180,
) -> list:
    """Return a NEW list of Episode copies with transcript_content scrubbed.

    Does not mutate the input episodes. Safe to use as a short-lived copy
    passed into the next generate_script() call during the dedup expansion
    loop. Per-episode scrubbing failures are logged but do not abort — the
    affected episode retains its original transcript.
    """
    if not saturated_topics:
        return list(episodes)

    # Minimum transcript length after scrubbing — below this we consider the
    # episode "gutted" and revert it to the original. Keeps the downstream
    # generator from choking on empty transcripts (it requires >=1000 chars).
    MIN_POST_SCRUB_CHARS = 1500

    cleaned_episodes = []
    total_before = 0
    total_after = 0
    scrubbed_count = 0
    reverted_count = 0

    for ep in episodes:
        # Use copy.copy so scores dict is shared but we can reassign transcript
        new_ep = copy.copy(ep)
        original_transcript = ep.transcript_content or ""
        cleaned, result = scrub_transcript(
            original_transcript,
            saturated_topics,
            timeout=timeout,
        )
        # If scrubbing removed almost everything, the episode is entirely
        # about a saturated topic. Revert to original so the generator still
        # has something to work with; the SATURATED prompt directive + dedup
        # pass will handle it at the output end.
        if not result.skipped and len(cleaned) < MIN_POST_SCRUB_CHARS:
            logger.info(
                f"Transcript scrub gutted episode '{ep.title[:50]}' "
                f"({result.chars_before} -> {len(cleaned)} chars); reverting to original"
            )
            new_ep.transcript_content = original_transcript
            total_before += result.chars_before
            total_after += result.chars_before
            reverted_count += 1
        else:
            new_ep.transcript_content = cleaned
            total_before += result.chars_before
            total_after += result.chars_after
            if not result.skipped:
                scrubbed_count += 1
        cleaned_episodes.append(new_ep)

    # Additional safety: if total content after scrub is less than 40% of
    # total before, abandon scrubbing entirely and return the originals.
    # This catches the "all episodes were saturated" case where even the
    # reverted ones plus the scrubbed ones don't have enough content to
    # write a coherent digest.
    if total_before > 0 and total_after < total_before * 0.4:
        logger.warning(
            f"Transcript scrub wiped {((total_before - total_after) / total_before) * 100:.0f}% "
            f"of total content ({total_before} -> {total_after}); abandoning scrub, "
            f"returning original episodes"
        )
        return list(episodes)

    logger.info(
        f"Transcript scrub summary: {scrubbed_count}/{len(episodes)} cleaned, "
        f"{reverted_count} reverted (gutted), "
        f"{total_before} -> {total_after} chars "
        f"({total_after - total_before:+d})"
    )
    return cleaned_episodes
