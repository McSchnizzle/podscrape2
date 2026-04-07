"""
Post-generation deduplication pass (v3.26+).

Problem solved: even with the story-arc tracking system, daily digests retell the
same story (Claude Code leak, OpenAI fundraising) across many consecutive days
because each source podcast re-explains the background from scratch.

This module runs after the main script generator produces a draft, compares the
draft against the last N digest scripts for the same topic, and uses `claude -p`
(via the existing Max subscription — no API cost) to rewrite repeated beats as
one-line "quick update" references while keeping genuinely new developments.

Used from `src/generation/script_generator.create_digest()`.
"""
from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Optional

logger = logging.getLogger(__name__)


class DedupPassError(Exception):
    """Raised when the dedup pass fails unrecoverably."""


@dataclass
class DedupResult:
    rewritten_script: str
    chars_before: int
    chars_after: int
    lookback_count: int
    skipped: bool = False
    skip_reason: Optional[str] = None
    # Notes for logging/audit
    notes: List[str] = field(default_factory=list)

    @property
    def delta(self) -> int:
        return self.chars_after - self.chars_before


# ---------------------------------------------------------------------------
# claude -p wrapper (same pattern as ScriptGenerator._call_claude_p)
# ---------------------------------------------------------------------------

def _call_claude_p(system_prompt: str, user_prompt: str, timeout: int = 1200) -> str:
    """Call Claude via `claude -p` in programmatic mode.

    Mirrors the pattern in src/generation/script_generator.py so both passes use
    the same subscription-backed path and avoid per-token API billing.
    """
    claude_path = os.path.expanduser("~/.local/bin/claude")
    if not os.path.exists(claude_path):
        claude_path = "claude"  # Fall back to PATH

    full_prompt = f"{system_prompt}\n\n{user_prompt}"

    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    env.pop("ANTHROPIC_API_KEY", None)

    result = subprocess.run(
        [
            claude_path, "-p",
            "--model", "sonnet",
            "--effort", "medium",
            "--tools", "",
            "--no-session-persistence",
            "-",
        ],
        input=full_prompt,
        stdin=None,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )

    if result.returncode != 0:
        raise DedupPassError(
            f"claude -p failed (exit {result.returncode}): {result.stderr[:500]}"
        )

    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_DEDUP_SYSTEM_PROMPT = """You are the editor for a daily two-host podcast digest. \
Your job is to prevent the show from repeating itself across days.

You will receive:
1. The current DRAFT script (today's digest).
2. The most recent PRIOR digest scripts for the same topic (oldest first).

Your goal: rewrite the DRAFT so that stories the audience already heard in the
prior digests are NOT re-introduced. Our listeners follow the show daily —
retelling "OpenAI raised $12 billion at an $852 billion valuation" for the fifth
day in a row makes the show unlistenable.

DECISION RULES for each story beat in the DRAFT:

1. REMOVE — if the story was already saturated in prior digests (covered 3+
   times with the same facts and no new development). Cut it entirely.

2. COMPRESS — if prior digests already introduced the story but today's draft
   includes a genuinely new wrinkle (a reversal, a new data point, a response,
   a consequence), rewrite the block as ONE short update that:
     - Explicitly references prior coverage ("Quick update on the OpenAI
       round...", "Since we covered the Claude Code leak...", "New wrinkle on
       the story we've been tracking about X...")
     - Skips the background explanation entirely.
     - Delivers only the new fact in 2-4 sentences.

3. KEEP — if the story is genuinely new today and did not appear (or appeared
   only glancingly) in prior digests, leave it alone.

HARD PRESERVATION RULES:
- Preserve speaker labels exactly: SPEAKER_1: and SPEAKER_2: on their own lines.
- Preserve audio tags exactly: [excited], [thoughtful], [serious], [laughs], etc.
- Preserve the intro and outro turns unless they re-introduce a saturated story.
- Do NOT add new facts that were not in the draft.
- Do NOT add commentary, headers, markdown, or meta-notes.
- Do NOT pad the script — if content is gone, the script is shorter. That is
  fine. Do not fabricate filler.
- Keep the two-host rhythm. If you compress a block that was split across both
  speakers, one speaker can now deliver the compressed update alone.

AI-WRITING HYGIENE (these rules carry over from the main generator — do not
violate them when rewriting):
- Keep contractions (isn't, don't, can't).
- No em dashes introduced by you. Use commas, semicolons, colons, or separate
  sentences.
- No manufactured disagreement between hosts. They are curators, not pundits.
- No "genuinely," "the framing," "throughline," "deep dive," "worth noting,"
  "both things can be true," "I want to push back," "I honestly don't know."

OUTPUT:
Return ONLY the rewritten DRAFT script. No preamble, no explanation, no diff,
no notes. Just the script content ready to be sent to TTS.
"""


def _build_user_prompt(draft_script: str, prior_scripts: List[dict]) -> str:
    """Build the user prompt with the draft and prior digests.

    prior_scripts is a list of {date, content} dicts, oldest first.
    """
    parts: List[str] = []
    parts.append("=== PRIOR DIGESTS (oldest first) ===\n")
    for i, prior in enumerate(prior_scripts, start=1):
        date = prior.get("date", "unknown")
        content = prior.get("content", "") or ""
        parts.append(f"\n--- PRIOR DIGEST {i} of {len(prior_scripts)} ({date}) ---\n")
        parts.append(content)
        parts.append("\n")
    parts.append("\n=== END PRIOR DIGESTS ===\n\n")
    parts.append("=== TODAY'S DRAFT (rewrite this) ===\n")
    parts.append(draft_script)
    parts.append("\n=== END DRAFT ===\n")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_dedup_pass(
    draft_script: str,
    topic: str,
    *,
    lookback: int = 8,
    digest_repo=None,
    exclude_digest_id: Optional[int] = None,
    timeout: int = 1500,
) -> DedupResult:
    """Run the post-generation dedup pass.

    Args:
        draft_script: The freshly generated script (before TTS).
        topic: Digest topic (e.g., "AI and Technology") used to scope lookback.
        lookback: How many prior digests to compare against (default 8).
        digest_repo: Optional DigestRepository; if None, one is created.
        exclude_digest_id: Skip this digest id when fetching priors (so a
            dedup re-run on an already-saved digest doesn't see itself).
        timeout: Subprocess timeout in seconds.

    Returns:
        DedupResult with the rewritten script and audit info. If the pass
        cannot run or fails safely, `skipped=True` and the original draft is
        returned unchanged.
    """
    chars_before = len(draft_script)

    if not draft_script or chars_before < 500:
        return DedupResult(
            rewritten_script=draft_script,
            chars_before=chars_before,
            chars_after=chars_before,
            lookback_count=0,
            skipped=True,
            skip_reason="draft too short to dedup",
        )

    # Fetch prior digests for this topic
    try:
        prior = _fetch_prior_digests(
            topic=topic,
            limit=lookback,
            digest_repo=digest_repo,
            exclude_digest_id=exclude_digest_id,
        )
    except Exception as e:
        logger.warning(f"Dedup pass: failed to fetch prior digests: {e}")
        return DedupResult(
            rewritten_script=draft_script,
            chars_before=chars_before,
            chars_after=chars_before,
            lookback_count=0,
            skipped=True,
            skip_reason=f"prior fetch failed: {e}",
        )

    if not prior:
        logger.info(f"Dedup pass: no prior digests for '{topic}', skipping")
        return DedupResult(
            rewritten_script=draft_script,
            chars_before=chars_before,
            chars_after=chars_before,
            lookback_count=0,
            skipped=True,
            skip_reason="no prior digests",
        )

    logger.info(
        f"Dedup pass: {chars_before} char draft vs {len(prior)} prior digests "
        f"for '{topic}'"
    )

    user_prompt = _build_user_prompt(draft_script, prior)

    try:
        revised = _call_claude_p(
            _DEDUP_SYSTEM_PROMPT,
            user_prompt,
            timeout=timeout,
        ).strip()
    except subprocess.TimeoutExpired:
        logger.warning("Dedup pass: claude -p timed out, keeping original draft")
        return DedupResult(
            rewritten_script=draft_script,
            chars_before=chars_before,
            chars_after=chars_before,
            lookback_count=len(prior),
            skipped=True,
            skip_reason="claude -p timeout",
        )
    except DedupPassError as e:
        logger.warning(f"Dedup pass: claude -p failed, keeping original draft: {e}")
        return DedupResult(
            rewritten_script=draft_script,
            chars_before=chars_before,
            chars_after=chars_before,
            lookback_count=len(prior),
            skipped=True,
            skip_reason=str(e),
        )

    chars_after = len(revised)

    # --- Safety validations ---

    # 1. If result is implausibly small (<10% of original), something went wrong.
    # v3.27: lowered from 0.3 to 0.1 because aggressive dedup against 8 saturated
    # priors can legitimately cut ~85% when a day's transcripts are almost
    # entirely rehashed content. The dynamic-expansion retry loop will pull
    # more episodes if the result is below the target floor but above 10%.
    if chars_after < chars_before * 0.1:
        logger.warning(
            f"Dedup pass result catastrophically short "
            f"({chars_after} vs {chars_before}); keeping original"
        )
        return DedupResult(
            rewritten_script=draft_script,
            chars_before=chars_before,
            chars_after=chars_before,
            lookback_count=len(prior),
            skipped=True,
            skip_reason="result too short",
        )

    # 2. Speaker labels must be preserved for dialogue scripts.
    if "SPEAKER_1:" in draft_script or "SPEAKER_2:" in draft_script:
        if "SPEAKER_1:" not in revised or "SPEAKER_2:" not in revised:
            logger.warning("Dedup pass broke speaker labels; keeping original")
            return DedupResult(
                rewritten_script=draft_script,
                chars_before=chars_before,
                chars_after=chars_before,
                lookback_count=len(prior),
                skipped=True,
                skip_reason="speaker labels broken",
            )

    # 3. Result should not be LONGER than original (dedup can only remove).
    if chars_after > int(chars_before * 1.05):
        logger.warning(
            f"Dedup pass expanded script ({chars_after} > {chars_before}); "
            "keeping original"
        )
        return DedupResult(
            rewritten_script=draft_script,
            chars_before=chars_before,
            chars_after=chars_before,
            lookback_count=len(prior),
            skipped=True,
            skip_reason="result longer than draft",
        )

    logger.info(
        f"Dedup pass complete: {chars_before} -> {chars_after} chars "
        f"({chars_after - chars_before:+d}, lookback={len(prior)})"
    )

    return DedupResult(
        rewritten_script=revised,
        chars_before=chars_before,
        chars_after=chars_after,
        lookback_count=len(prior),
        skipped=False,
    )


# ---------------------------------------------------------------------------
# Fetching prior digests
# ---------------------------------------------------------------------------

def _fetch_prior_digests(
    topic: str,
    limit: int,
    digest_repo=None,
    exclude_digest_id: Optional[int] = None,
) -> List[dict]:
    """Fetch the last `limit` digest scripts for a topic, excluding one id.

    Returns a list of {date, content} dicts, oldest first.
    """
    # Direct SQLAlchemy query is simpler and more portable than adding a new
    # repo method for this one use case.
    from src.database.models import get_database_manager
    from src.database.sqlalchemy_models import Digest as DigestModel

    db = get_database_manager()
    with db.get_session() as session:
        query = session.query(DigestModel).filter(
            DigestModel.topic == topic,
            DigestModel.script_content.isnot(None),
        )
        if exclude_digest_id is not None:
            query = query.filter(DigestModel.id != exclude_digest_id)

        rows = (
            query.order_by(DigestModel.generated_at.desc())
            .limit(limit)
            .all()
        )

        # Return oldest first so prompt reads chronologically
        rows = list(reversed(rows))
        return [
            {
                "id": r.id,
                "date": r.digest_date.isoformat() if r.digest_date else "unknown",
                "content": r.script_content or "",
            }
            for r in rows
        ]
