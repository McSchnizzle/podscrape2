"""Watch-theme scan primitive: claude -p per-episode/per-theme excerpt matcher.

Extracted from scripts/run_watch_digest.py (no behavior change to the
weekly path -- run_watch_digest.py now imports scan_episode_for_theme from
here) so the nightly daily-emphasis pass in
src/generation/script_generator.py can reuse the same claude -p wrapper
instead of duplicating it.

Two entry points:
  - scan_episode_for_theme: ONE episode x ONE theme, ONE claude -p call.
    Used by the weekly Sunday digest, which scans every AI&Tech episode in
    a 7-day window independently per theme.
  - scan_episodes_for_daily_emphasis: MANY episodes x ONE theme, ONE
    claude -p call (batched). Used by the nightly Tier B emphasis pass,
    which bounds cost to exactly one call per active daily/both theme
    regardless of how many episodes are in that night's digest.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from typing import List

logger = logging.getLogger("watch_theme_scan")

# The only topic watch themes ever scan against -- both the weekly digest
# and the nightly Tier B emphasis pass are AI & Technology-only.
WATCH_THEME_TOPIC = "AI and Technology"

CLAUDE_TIMEOUT_SECONDS = 300


def _call_claude_p(system_prompt: str, user_prompt: str, timeout: int) -> str:
    claude_path = os.path.expanduser("~/.local/bin/claude")
    if not os.path.exists(claude_path):
        claude_path = "claude"
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    env.pop("ANTHROPIC_API_KEY", None)
    full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"
    result = subprocess.run(
        [claude_path, "-p", "--model", "sonnet", "--effort", "low",
         "--tools", "", "--no-session-persistence", "-"],
        input=full_prompt,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude -p failed ({result.returncode}): {result.stderr[:300]}")
    return result.stdout.strip()


def _parse_match_array(raw: str, context: str) -> List[dict]:
    """Shared JSON-array parsing for both scan functions below."""
    if raw.startswith("```"):
        raw = raw.strip("`").lstrip("json").strip()
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [m for m in parsed
                    if isinstance(m, dict) and m.get("excerpt")]
    except json.JSONDecodeError:
        logger.warning(f"Non-JSON response from {context}: {raw[:200]}")
    return []


# ---------------------------------------------------------------------------
# Weekly path: one episode x one theme per call
# ---------------------------------------------------------------------------

_SCAN_SYSTEM_PROMPT = """\
You are scanning a podcast transcript for excerpts that match a specific
user-defined theme. You will receive:
1. THEME: the user's description of what they care about
2. TRANSCRIPT: one episode's transcript

Return a JSON array of matching excerpts. Each excerpt object has:
  - "excerpt": verbatim text from the transcript, 50–400 chars, trimmed cleanly
  - "note": 1 short sentence explaining why this excerpt matches the theme

Return only genuinely strong matches. It is OK to return an empty array if
the episode does not meaningfully discuss the theme. Prefer quality over
quantity — 0–3 excerpts per episode is typical.

Do NOT paraphrase. Only return verbatim quotes from the transcript.

Output ONLY the JSON array. No preamble, no explanation, no markdown fence.
"""


def scan_episode_for_theme(
    transcript: str,
    theme_name: str,
    theme_description: str,
    episode_title: str,
) -> List[dict]:
    """Return list of {excerpt, note} dicts from claude -p for ONE episode."""
    max_transcript = 60_000
    trimmed = transcript[:max_transcript]
    user_prompt = (
        f"## THEME: {theme_name}\n\n"
        f"{theme_description}\n\n"
        f"## TRANSCRIPT: {episode_title}\n\n"
        f"{trimmed}\n\n---\n\n"
        f"Return the JSON array of matches now."
    )
    try:
        raw = _call_claude_p(_SCAN_SYSTEM_PROMPT, user_prompt, CLAUDE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        logger.warning(f"Theme scan timeout: {theme_name} / {episode_title[:50]}")
        return []
    except Exception as e:
        logger.warning(f"Theme scan failed: {theme_name} / {episode_title[:50]}: {e}")
        return []

    return _parse_match_array(raw, context=f"theme scan ({theme_name} / {episode_title[:50]})")


# ---------------------------------------------------------------------------
# Daily path: many episodes x one theme, ONE batched call
# ---------------------------------------------------------------------------

_BATCH_SCAN_SYSTEM_PROMPT = """\
You are scanning several podcast episode transcripts -- all being produced
into tonight's single digest episode -- for material matching ONE
user-defined theme. You will receive:
1. THEME: the user's description of what they care about
2. EPISODES: multiple transcripts, each labeled with its exact title

Return a JSON array of matching excerpts. Each object has:
  - "episode_title": the EXACT title of the episode the excerpt came from,
    copied verbatim from its "## Episode:" label below
  - "excerpt": verbatim text from that transcript, 50–400 chars, trimmed cleanly
  - "note": 1 short sentence explaining why this excerpt matches the theme

Return only genuinely strong matches across ALL episodes combined. It is OK
to return an empty array if none of the episodes meaningfully discuss the
theme. Prefer quality over quantity.

Do NOT paraphrase. Only return verbatim quotes from the transcripts.

Output ONLY the JSON array. No preamble, no explanation, no markdown fence.
"""


def scan_episodes_for_daily_emphasis(
    episodes: List[object],
    theme_name: str,
    theme_description: str,
    max_chars_per_episode: int = 8_000,
    timeout: int = CLAUDE_TIMEOUT_SECONDS,
) -> List[dict]:
    """Scan MULTIPLE episodes against ONE theme in a SINGLE claude -p call.

    Unlike scan_episode_for_theme (one call per episode), this bounds
    nightly cost to exactly one call per active daily/both watch theme,
    regardless of how many episodes are in that night's digest. Used by
    ScriptGenerator's Tier B daily-emphasis pass.

    `episodes` is duck-typed: any object with `.title` and
    `.transcript_content` attributes (SQLAlchemy Episode instances in
    production). Episodes with no transcript content are skipped.

    Returns a list of {"episode_title", "excerpt", "note"} dicts. Returns
    an empty list on any error (timeout, non-JSON, no usable episodes) --
    callers are expected to fail open and proceed without emphasis.
    """
    usable = [
        ep for ep in episodes
        if getattr(ep, "transcript_content", None) and ep.transcript_content.strip()
    ]
    if not usable:
        return []

    sections = []
    for ep in usable:
        trimmed = ep.transcript_content[:max_chars_per_episode]
        sections.append(f'## Episode: "{ep.title}"\n\n{trimmed}')

    user_prompt = (
        f"## THEME: {theme_name}\n\n{theme_description}\n\n"
        f"## EPISODES ({len(usable)})\n\n"
        + "\n\n---\n\n".join(sections)
        + "\n\n---\n\nReturn the JSON array of matches now."
    )

    try:
        raw = _call_claude_p(_BATCH_SCAN_SYSTEM_PROMPT, user_prompt, timeout)
    except subprocess.TimeoutExpired:
        logger.warning(f"Daily theme-emphasis scan timeout: {theme_name}")
        return []
    except Exception as e:
        logger.warning(f"Daily theme-emphasis scan failed: {theme_name}: {e}")
        return []

    return _parse_match_array(raw, context=f"daily theme-emphasis scan ({theme_name})")
