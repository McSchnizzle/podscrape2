#!/usr/bin/env python3
"""Weekly Watch Themes personal digest generator.

For each active watch_theme, scans the last 7 days of AI & Technology episode
transcripts (PT-anchored window), uses `claude -p` per-episode to extract
excerpts matching the theme, aggregates results into a single combined HTML
digest, emails to brownpr0@gmail.com via Microsoft Graph, and POSTs the
digest to Harold's ingestion endpoint.

Run manually or via et01 cron (Sunday 7:00 AM Pacific).

Idempotency: upserts `watch_digest_runs` on `run_date` (Sunday date in PT).
Re-running the same Sunday replaces the prior row but still re-sends email
and re-POSTs to Harold. Harold should upsert on `date` to avoid dupes.
"""
from __future__ import annotations

import argparse
import html
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import List, Optional
from zoneinfo import ZoneInfo

# Allow running as a script from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parent.parent / '.env')

from sqlalchemy import text  # noqa: E402

from src.database.models import get_database_manager  # noqa: E402
from src.database.sqlalchemy_models import (  # noqa: E402
    Episode, WatchTheme, WatchDigestRun,
)
from src.utils.timezone import get_pacific_now  # noqa: E402

logger = logging.getLogger("watch_digest")

TOPIC = "AI and Technology"
SCORE_THRESHOLD = 0.65
WINDOW_DAYS = 7
CLAUDE_TIMEOUT_SECONDS = 300


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

@dataclass
class ThemeMatch:
    """A single matched excerpt for one theme from one episode."""
    episode_id: int
    episode_title: str
    episode_date: date
    excerpt: str
    relevance_note: str = ""


@dataclass
class ThemeResult:
    """All matches for a single theme across the week."""
    theme_id: int
    theme_name: str
    theme_description: str
    matches: List[ThemeMatch] = field(default_factory=list)
    episodes_scanned: int = 0
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Weekly window
# ---------------------------------------------------------------------------

def compute_window(now_pt: Optional[datetime] = None) -> tuple[datetime, datetime, date]:
    """Return (window_start_utc, window_end_utc, run_date_pt).

    Window is the last 7 complete days in Pacific time ending at 'now'.
    run_date is the PT date of 'now' (the Sunday when run by cron).
    """
    pt = ZoneInfo("America/Los_Angeles")
    utc = ZoneInfo("UTC")
    now_pt = now_pt or get_pacific_now()
    if now_pt.tzinfo is None:
        now_pt = now_pt.replace(tzinfo=pt)
    window_end = now_pt.astimezone(utc)
    window_start = window_end - timedelta(days=WINDOW_DAYS)
    return window_start, window_end, now_pt.date()


# ---------------------------------------------------------------------------
# Claude -p wrapper — per-episode theme scan
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


def scan_episode_for_theme(
    transcript: str,
    theme_name: str,
    theme_description: str,
    episode_title: str,
) -> List[dict]:
    """Return list of {excerpt, note} dicts from claude -p."""
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

    # Strip common wrappers the model sometimes adds
    if raw.startswith("```"):
        raw = raw.strip("`").lstrip("json").strip()
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [m for m in parsed
                    if isinstance(m, dict) and m.get("excerpt")]
    except json.JSONDecodeError:
        logger.warning(f"Non-JSON response from theme scan: {raw[:200]}")
    return []


# ---------------------------------------------------------------------------
# HTML/markdown rendering
# ---------------------------------------------------------------------------

def render_html(run_date: date, theme_results: List[ThemeResult]) -> str:
    parts = [
        "<!DOCTYPE html>",
        '<html><head><meta charset="utf-8">',
        f"<title>Watch Themes — week of {run_date.isoformat()}</title>",
        "<style>body{font-family:-apple-system,system-ui,sans-serif;",
        "max-width:720px;margin:24px auto;padding:0 16px;line-height:1.5;color:#222;}",
        "h1{font-size:24px;margin-bottom:4px}",
        "h2{font-size:18px;margin-top:28px;border-bottom:1px solid #ddd;padding-bottom:4px}",
        ".meta{color:#666;font-size:13px;margin-bottom:16px}",
        ".match{margin:12px 0;padding:10px 12px;background:#f7f7fa;border-left:3px solid #7c8aff;border-radius:4px}",
        ".excerpt{margin:0;font-style:italic}",
        ".src{display:block;margin-top:6px;font-size:12px;color:#555}",
        ".note{margin-top:4px;font-size:13px;color:#444}",
        ".none{color:#888;font-style:italic}",
        "</style></head><body>",
        f"<h1>Watch Themes digest</h1>",
        f'<div class="meta">Week ending {run_date.isoformat()} · '
        f"{sum(len(t.matches) for t in theme_results)} matches across "
        f"{len(theme_results)} themes</div>",
    ]
    for tr in theme_results:
        parts.append(f"<h2>{html.escape(tr.theme_name)}</h2>")
        if tr.error:
            parts.append(f'<p class="none">Scan error: {html.escape(tr.error)}</p>')
            continue
        if not tr.matches:
            parts.append(
                f'<p class="none">No matches this week '
                f"(scanned {tr.episodes_scanned} episodes).</p>"
            )
            continue
        for m in tr.matches:
            parts.append('<div class="match">')
            parts.append(f'<p class="excerpt">&ldquo;{html.escape(m.excerpt)}&rdquo;</p>')
            if m.relevance_note:
                parts.append(f'<div class="note">{html.escape(m.relevance_note)}</div>')
            parts.append(
                f'<span class="src">— {html.escape(m.episode_title)} '
                f"({m.episode_date.isoformat()})</span>"
            )
            parts.append("</div>")
    parts.append("</body></html>")
    return "\n".join(parts)


def render_markdown(run_date: date, theme_results: List[ThemeResult]) -> str:
    lines = [f"# Watch Themes digest — week of {run_date.isoformat()}", ""]
    for tr in theme_results:
        lines.append(f"## {tr.theme_name}")
        lines.append("")
        if tr.error:
            lines.append(f"_Scan error: {tr.error}_")
        elif not tr.matches:
            lines.append(f"_No matches this week (scanned {tr.episodes_scanned} episodes)._")
        else:
            for m in tr.matches:
                lines.append(f"> {m.excerpt}")
                if m.relevance_note:
                    lines.append(f"_{m.relevance_note}_")
                lines.append(f"— **{m.episode_title}** ({m.episode_date.isoformat()})")
                lines.append("")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Delivery: email via Microsoft Graph (ai-coder)
# ---------------------------------------------------------------------------

def send_email_via_graph(html_body: str, run_date: date) -> bool:
    try:
        from azure.identity import ClientSecretCredential
        import httpx
    except ImportError:
        logger.error("Email deps missing; install azure-identity + httpx")
        return False

    required = ["EMAIL_AZURE_TENANT_ID", "EMAIL_AZURE_CLIENT_ID",
               "EMAIL_AZURE_CLIENT_SECRET"]
    if any(not os.getenv(k) for k in required):
        logger.error(f"Email env vars missing: {[k for k in required if not os.getenv(k)]}")
        return False

    cred = ClientSecretCredential(
        tenant_id=os.environ['EMAIL_AZURE_TENANT_ID'],
        client_id=os.environ['EMAIL_AZURE_CLIENT_ID'],
        client_secret=os.environ['EMAIL_AZURE_CLIENT_SECRET'],
    )
    token = cred.get_token('https://graph.microsoft.com/.default').token

    payload = {
        "message": {
            "subject": f"Watch Themes — week of {run_date.isoformat()}",
            "body": {"contentType": "HTML", "content": html_body},
            "toRecipients": [{"emailAddress": {"address": "brownpr0@gmail.com"}}],
        },
        "saveToSentItems": "true",
    }
    try:
        r = httpx.post(
            "https://graph.microsoft.com/v1.0/users/"
            "ai-coder@vital-enterprises.com/sendMail",
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
            content=json.dumps(payload),
            timeout=30,
        )
        if r.status_code == 202:
            logger.info("Email sent successfully")
            return True
        logger.error(f"Email send failed {r.status_code}: {r.text[:300]}")
        return False
    except Exception as e:
        logger.error(f"Email send exception: {e}")
        return False


# ---------------------------------------------------------------------------
# Delivery: POST to Harold
# ---------------------------------------------------------------------------

def post_to_harold(html_body: str, markdown_body: str, run_date: date) -> bool:
    import httpx
    base = os.getenv("HAROLD_BASE_URL", "https://harold.paulrbrown.org")
    secret = os.getenv("WATCH_DIGEST_SECRET")
    if not secret:
        logger.warning("WATCH_DIGEST_SECRET not set; skipping Harold POST")
        return False
    url = f"{base}/api/internal/watch-digest"
    payload = {"date": run_date.isoformat(), "html": html_body, "markdown": markdown_body}
    try:
        r = httpx.post(
            url,
            headers={"X-Internal-Secret": secret, "Content-Type": "application/json"},
            content=json.dumps(payload),
            timeout=30,
        )
        if 200 <= r.status_code < 300:
            logger.info(f"Harold POST succeeded ({r.status_code})")
            return True
        logger.warning(f"Harold POST returned {r.status_code}: {r.text[:300]}")
        return False
    except Exception as e:
        logger.warning(f"Harold POST exception (endpoint may not be deployed yet): {e}")
        return False


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def run(dry_run: bool = False, episode_limit: Optional[int] = None,
        theme_ids: Optional[List[int]] = None, no_summarize: bool = False) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    window_start, window_end, run_date = compute_window()
    logger.info(f"Watch digest run: window {window_start.isoformat()} — "
                f"{window_end.isoformat()} (PT run_date {run_date.isoformat()})")

    db = get_database_manager()

    # Short-lived session: load themes + episode data, release connection
    # before the long claude -p scan loop. Holding the session across many
    # minutes of scanning causes Supabase to drop the connection.
    with db.get_session() as session:
        q = session.query(WatchTheme).filter(WatchTheme.active.is_(True))
        if theme_ids:
            q = q.filter(WatchTheme.id.in_(theme_ids))
        themes_raw = q.order_by(WatchTheme.sort_order, WatchTheme.id).all()
        themes_data = [
            {"id": t.id, "name": t.name, "description": t.description}
            for t in themes_raw
        ]
        logger.info(f"Loaded {len(themes_data)} active watch themes "
                    f"{'(filtered)' if theme_ids else ''}")

        if not themes_data:
            logger.warning("No active watch themes; nothing to generate")
            return 0

        rows = session.execute(text(
            "SELECT id, title, published_date, transcript_content, scores "
            "FROM episodes "
            "WHERE published_date >= :start AND published_date <= :end "
            "AND status IN ('scored', 'digested') "
            "AND transcript_content IS NOT NULL "
            "ORDER BY published_date DESC"
        ), {"start": window_start, "end": window_end}).fetchall()

        episodes = []
        for r in rows:
            scores = r[4] if isinstance(r[4], dict) else {}
            score = float(scores.get(TOPIC, 0) or 0)
            if score >= SCORE_THRESHOLD:
                episodes.append({
                    "id": r[0], "title": r[1], "published_date": r[2],
                    "transcript": r[3], "score": score,
                })

    # Session released — scan loop runs DB-free
    if episode_limit and len(episodes) > episode_limit:
        episodes = episodes[:episode_limit]
        logger.info(f"Limiting to {episode_limit} most recent episodes")

    logger.info(f"Scanning {len(episodes)} AI&Tech episodes in window "
                f"(score >= {SCORE_THRESHOLD})")

    theme_results: List[ThemeResult] = []
    for theme in themes_data:
        logger.info(f"Theme: {theme['name']}")
        tr = ThemeResult(
            theme_id=theme['id'],
            theme_name=theme['name'],
            theme_description=theme['description'],
            episodes_scanned=len(episodes),
        )
        for ep in episodes:
            matches = scan_episode_for_theme(
                ep["transcript"], theme['name'], theme['description'], ep["title"],
            )
            for m in matches:
                excerpt = m.get("excerpt", "").strip()
                if len(excerpt) < 30:
                    continue
                tr.matches.append(ThemeMatch(
                    episode_id=ep["id"],
                    episode_title=ep["title"],
                    episode_date=ep["published_date"].date() if hasattr(
                        ep["published_date"], "date") else ep["published_date"],
                    excerpt=excerpt[:400],
                    relevance_note=m.get("note", "").strip()[:200],
                ))
        logger.info(f"  → {len(tr.matches)} matches")
        theme_results.append(tr)

    raw_html = render_html(run_date, theme_results)
    raw_md = render_markdown(run_date, theme_results)
    logger.info(f"Rendered raw: {len(raw_html):,} chars HTML / {len(raw_md):,} chars MD")

    if dry_run:
        dry_dir = Path("data/watch-digests")
        dry_dir.mkdir(parents=True, exist_ok=True)
        raw_path = dry_dir / f"{run_date.isoformat()}-raw.md"
        raw_path.write_text(raw_md)
        logger.info(f"Dry-run: wrote raw {raw_path}")
        # Also run summarizer in dry-run so Paul can inspect both
        if not no_summarize:
            summarized_md, summarized_html = _summarize(run_date, raw_md)
            sum_path = dry_dir / f"{run_date.isoformat()}-summary-dryrun.md"
            sum_path.write_text(summarized_md)
            logger.info(f"Dry-run: wrote summary {sum_path}")
        return 0

    # v3.41: Default delivery is the SUMMARIZED version (shape C). Raw excerpts
    # are still saved to the audit row so a re-summarization pass can replay
    # them with an updated SYNTHESIS_PROMPT. --no-summarize flag bypasses.
    if no_summarize:
        delivery_html = raw_html
        delivery_md = raw_md
        logger.info("--no-summarize: delivering raw digest")
    else:
        delivery_md, delivery_html = _summarize(run_date, raw_md)
        logger.info(f"Summarized: {len(delivery_html):,} chars HTML / {len(delivery_md):,} chars MD")

    email_ok = send_email_via_graph(delivery_html, run_date)
    harold_ok = post_to_harold(delivery_html, delivery_md, run_date)

    # Upsert audit row — store RAW markdown (for re-summarization) + delivered HTML
    with db.get_session() as session:
        existing = session.query(WatchDigestRun).filter_by(run_date=run_date).first()
        common = {
            "window_start": window_start,
            "window_end": window_end,
            "themes_scanned": len(theme_results),
            "episodes_scanned": len(episodes),
            "html_content": delivery_html,
            "markdown_content": raw_md,  # raw stored for re-summarization
            "email_delivered": email_ok,
            "harold_delivered": harold_ok,
        }
        if existing:
            for k, v in common.items():
                setattr(existing, k, v)
        else:
            session.add(WatchDigestRun(run_date=run_date, **common))
        session.commit()

    return 0 if (email_ok or harold_ok) else 1


def _summarize(run_date: "date", raw_md: str) -> tuple[str, str]:
    """Run the shape-C synthesis pass. Delegates to summarize_watch_digest
    so there's one source of truth for the SYNTHESIS_PROMPT.
    """
    import summarize_watch_digest as sw
    themes = sw.parse_themes(raw_md)
    summaries = [(t.name, sw.summarize_theme(t)) for t in themes]
    date_header = f"Watch Themes digest — week of {run_date.isoformat()}"
    md = sw.render_summarized_markdown(date_header, summaries)
    html_out = sw.render_summarized_html(date_header, summaries)
    return md, html_out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Write HTML to disk, skip email + Harold POST")
    parser.add_argument("--episode-limit", type=int, default=None,
                        help="Scan only the N most-recent episodes (for testing)")
    parser.add_argument("--theme-ids", type=str, default=None,
                        help="Comma-separated watch_theme IDs to scan (for testing)")
    parser.add_argument("--no-summarize", action="store_true",
                        help="Skip shape-C summarization; deliver raw excerpts")
    args = parser.parse_args()
    theme_ids = None
    if args.theme_ids:
        theme_ids = [int(x) for x in args.theme_ids.split(",") if x.strip()]
    sys.exit(run(dry_run=args.dry_run, episode_limit=args.episode_limit,
                 theme_ids=theme_ids, no_summarize=args.no_summarize))
