"""
Hot-briefing auto-generation (v3.27+).

When a story arc crosses the "hot" thresholds (5+ events OR 3+ sources),
automatically generate a 2-3 sentence `hot_briefing` via `claude -p` and mark
the arc as hot. This briefing is then injected into the script generator prompt
under "HOT STORY BRIEFINGS" with the directive "audience already knows the
background, focus on what's NEW."

This replaces the manual/never-happens path where briefings had to be written
by a human. Called from topic_extractor after events are added to arcs.
"""
from __future__ import annotations

import logging
import os
import subprocess
from typing import List, Optional

logger = logging.getLogger(__name__)


# Thresholds for auto-promoting an arc to "hot"
HOT_EVENT_THRESHOLD = 5
HOT_SOURCE_THRESHOLD = 3


class HotBriefingError(Exception):
    pass


def _call_claude_p(system_prompt: str, user_prompt: str, timeout: int = 300) -> str:
    """Run `claude -p` and return stdout. Same pattern as ScriptGenerator."""
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
        raise HotBriefingError(
            f"claude -p failed (exit {result.returncode}): {result.stderr[:300]}"
        )
    return result.stdout.strip()


_BRIEFING_SYSTEM_PROMPT = """You write short background briefings for an ongoing \
podcast digest that tracks news stories over time. Your output becomes the shared \
"audience already knows" baseline so future episodes don't re-introduce this \
story from scratch.

Requirements:
- 2 to 3 sentences, no more.
- Cover the core facts (who, what, when, where) concisely.
- Neutral tone. No speculation, no editorial voice, no rhetorical questions.
- No host dialogue, no audio tags, no markdown, no bullet points.
- Plain prose only. Output nothing but the briefing text.
"""


def _build_briefing_user_prompt(arc_name: str, events: List[dict]) -> str:
    """Build the user prompt from an arc and its events."""
    lines = [f"Story arc: {arc_name}", "", "Events (chronological):"]
    # Sort by event_date ascending
    sorted_events = sorted(events, key=lambda e: e.get("event_date") or "")
    for i, ev in enumerate(sorted_events, start=1):
        summary = ev.get("event_summary") or ""
        source = ev.get("source_name") or "unknown"
        date = ev.get("event_date") or "unknown"
        if hasattr(date, "isoformat"):
            date = date.isoformat()
        lines.append(f"{i}. [{date}] ({source}) {summary}")
        key_points = ev.get("key_points") or []
        if isinstance(key_points, list):
            for kp in key_points[:3]:
                lines.append(f"   - {kp}")
    lines.append("")
    lines.append(
        "Write a 2-3 sentence briefing summarizing this story arc so far. "
        "Output only the briefing text."
    )
    return "\n".join(lines)


def should_promote_to_hot(event_count: int, source_count: int) -> bool:
    """Return True if an arc meets the 'hot' threshold."""
    return event_count >= HOT_EVENT_THRESHOLD or source_count >= HOT_SOURCE_THRESHOLD


def generate_hot_briefing_for_arc(arc_id: int, *, timeout: int = 120) -> Optional[str]:
    """Generate and persist a hot briefing for an existing arc.

    Fetches the arc and its events from the repo, calls `claude -p`, saves the
    result to the arc's `hot_briefing` column, and sets `is_hot = True`.

    Returns the generated briefing text, or None on failure/no-op.
    """
    from src.database.story_arc_repo import get_story_arc_repo
    from src.database.models import get_database_manager
    from src.database.sqlalchemy_models import StoryArc

    repo = get_story_arc_repo()
    arc_dict = repo.get_story_arc_by_id(arc_id)
    if not arc_dict:
        logger.warning(f"Hot briefing: arc {arc_id} not found")
        return None

    event_count = arc_dict.get("event_count") or 0
    source_count = arc_dict.get("source_count") or 0

    if not should_promote_to_hot(event_count, source_count):
        return None

    if arc_dict.get("hot_briefing"):
        # Already has a briefing — only regenerate if significantly more events
        # have been added since last briefing. For simplicity, skip here.
        return None

    arc_name = arc_dict.get("arc_name") or "Unknown arc"
    events = arc_dict.get("events") or []

    if not events:
        logger.info(
            f"Hot briefing: arc {arc_id} '{arc_name}' has no events, skipping"
        )
        return None

    # v3.29: skip if claude -p is broken on this host
    try:
        from src.utils.claude_p_health import is_claude_p_healthy
        if not is_claude_p_healthy():
            logger.info(f"Hot briefing: skipping arc {arc_id} (claude -p unhealthy)")
            return None
    except Exception:
        pass

    try:
        briefing = _call_claude_p(
            _BRIEFING_SYSTEM_PROMPT,
            _build_briefing_user_prompt(arc_name, events),
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        logger.warning(f"Hot briefing: claude -p timed out for arc {arc_id}")
        try:
            from src.utils.claude_p_health import mark_unhealthy
            mark_unhealthy(f"hot briefing arc {arc_id} timeout")
        except Exception:
            pass
        return None
    except HotBriefingError as e:
        logger.warning(f"Hot briefing: claude -p failed for arc {arc_id}: {e}")
        return None

    if not briefing or len(briefing) < 20:
        logger.warning(f"Hot briefing: result too short for arc {arc_id}, skipping")
        return None

    # Persist to DB
    db = get_database_manager()
    with db.get_session() as session:
        arc = session.query(StoryArc).filter(StoryArc.id == arc_id).first()
        if not arc:
            return None
        arc.hot_briefing = briefing
        arc.is_hot = True
        session.commit()

    logger.info(
        f"Hot briefing generated for arc {arc_id} '{arc_name}': "
        f"{len(briefing)} chars, events={event_count}, sources={source_count}"
    )
    return briefing


def maybe_generate_hot_briefing(arc_id: int, event_count: int, source_count: int) -> None:
    """Best-effort: promote an arc to hot if thresholds crossed and no briefing yet.

    Swallows all exceptions — this is a background nicety and must never break
    the caller's event-add flow.
    """
    try:
        if should_promote_to_hot(event_count, source_count):
            generate_hot_briefing_for_arc(arc_id)
    except Exception as e:
        logger.warning(f"Hot briefing auto-generation failed for arc {arc_id}: {e}")
