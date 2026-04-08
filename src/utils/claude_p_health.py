"""
Cached health probe for `claude -p` (v3.29+).

Background: on 2026-04-07 the production cron got stuck because the
`claude -p` CLI on et01 had been auto-updated to a buggy version that hung
on every invocation. Each of the four claude -p call sites (script
structural-variety pass, dedup pass, transcript scrubber, hot-briefing
generator) hit its individual subprocess timeout one after another and
collectively burned the entire 2-hour cron-wrapper budget without ever
producing a digest.

This module provides a single cached health probe that runs ONCE per
process. All claude -p call sites consult it before attempting work and
short-circuit gracefully if the CLI is broken. The pipeline still produces
a digest in that case — just without the optional dedup / scrubbing /
briefing features that depend on claude -p.

Usage:

    from src.utils.claude_p_health import is_claude_p_healthy

    if not is_claude_p_healthy():
        logger.warning("Skipping dedup pass: claude -p is unhealthy")
        return

The first caller pays the probe cost (~1-3 sec when healthy, up to
PROBE_TIMEOUT when broken). Subsequent callers get the cached result for
free. The cache is process-lifetime; a new pipeline run gets a fresh probe.
"""
from __future__ import annotations

import logging
import os
import subprocess
import threading
from typing import Optional

logger = logging.getLogger(__name__)

# Probe timeout — kept tight so a broken claude -p costs us at most this
# many seconds total per pipeline run, not per-call.
PROBE_TIMEOUT = 20  # seconds

_lock = threading.Lock()
_cached: Optional[bool] = None


def _claude_path() -> str:
    p = os.path.expanduser("~/.local/bin/claude")
    return p if os.path.exists(p) else "claude"


def _run_probe() -> bool:
    """Run a minimal claude -p call and return True if it responds quickly.

    Uses the exact same flags as production callers so the probe is
    representative. Sends a one-token prompt and discards the output.
    """
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    env.pop("ANTHROPIC_API_KEY", None)

    try:
        result = subprocess.run(
            [
                _claude_path(), "-p",
                "--model", "sonnet",
                "--effort", "medium",
                "--tools", "",
                "--no-session-persistence",
                "-",
            ],
            input="reply with the single word OK and nothing else",
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT,
            env=env,
        )
    except subprocess.TimeoutExpired:
        logger.warning(
            f"claude -p health probe TIMED OUT after {PROBE_TIMEOUT}s — "
            f"all claude-p features will be skipped this run"
        )
        return False
    except FileNotFoundError:
        logger.warning(
            "claude -p health probe FAILED: CLI binary not found — "
            "all claude-p features will be skipped this run"
        )
        return False
    except Exception as e:
        logger.warning(
            f"claude -p health probe FAILED with exception ({e}) — "
            f"all claude-p features will be skipped this run"
        )
        return False

    if result.returncode != 0:
        logger.warning(
            f"claude -p health probe FAILED (exit {result.returncode}): "
            f"{result.stderr[:300]} — all claude-p features will be skipped"
        )
        return False

    out = (result.stdout or "").strip()
    if not out:
        logger.warning(
            "claude -p health probe returned empty output — "
            "all claude-p features will be skipped this run"
        )
        return False

    logger.info(
        f"claude -p health probe OK: replied {out[:40]!r} — "
        f"claude-p features enabled"
    )
    return True


def is_claude_p_healthy() -> bool:
    """Return True if `claude -p` is responsive. Cached per process.

    Thread-safe: only one probe runs even under concurrent first-callers.
    """
    global _cached
    if _cached is not None:
        return _cached

    with _lock:
        if _cached is not None:
            return _cached
        _cached = _run_probe()
        return _cached


def reset_health_cache() -> None:
    """Force the next is_claude_p_healthy() call to re-probe.

    Intended for tests and for long-running processes that want to retry
    after a known recovery event. Production cron runs do not need this.
    """
    global _cached
    with _lock:
        _cached = None
