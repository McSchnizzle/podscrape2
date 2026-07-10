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
import json
import logging
import os
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
from src.watch.theme_scan import scan_episode_for_theme  # noqa: E402
from src.watch import email_render  # noqa: E402

logger = logging.getLogger("watch_digest")

TOPIC = "AI and Technology"
SCORE_THRESHOLD = 0.65
WINDOW_DAYS = 7


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
# HTML/markdown rendering
# ---------------------------------------------------------------------------

def render_html(run_date: date, theme_results: List[ThemeResult]) -> str:
    """Render the raw (un-summarized) digest as a Harold UI email.

    Used for --dry-run inspection and the --no-summarize delivery path.
    Shares the same email shell as the default summarized delivery (see
    scripts/summarize_watch_digest.py::render_summarized_html) so both
    variants are visually one product.
    """
    total_matches = sum(len(t.matches) for t in theme_results)
    body_parts = []
    for tr in theme_results:
        if tr.error:
            body_parts.append(email_render.render_no_match_line(
                tr.theme_name, detail=f"scan error: {tr.error}"))
            continue
        if not tr.matches:
            body_parts.append(email_render.render_no_match_line(
                tr.theme_name,
                detail=f"no matches this week (scanned {tr.episodes_scanned} episodes)"))
            continue
        body_parts.append(email_render.render_theme_card_raw(tr.theme_name, tr.matches))

    return email_render.render_shell(
        eyebrow=f"WEEK OF {run_date.isoformat()}",
        masthead="Watch Themes",
        subtitle=f"{total_matches} matches across {len(theme_results)} themes (raw excerpts)",
        body_html="".join(body_parts),
        footer_note="Watch Themes · generated automatically from your podcast transcripts",
    )


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

def load_active_weekly_themes(session, theme_ids: Optional[List[int]] = None) -> List[dict]:
    """Active watch themes eligible for the Sunday digest: scope in
    ('weekly', 'both'). scope='daily' themes are nightly-emphasis-only (see
    ScriptGenerator._build_daily_theme_emphasis) and must NOT leak into the
    weekly email/Harold POST.
    """
    q = (
        session.query(WatchTheme)
        .filter(WatchTheme.active.is_(True))
        .filter(WatchTheme.scope.in_(['weekly', 'both']))
    )
    if theme_ids:
        q = q.filter(WatchTheme.id.in_(theme_ids))
    themes_raw = q.order_by(WatchTheme.sort_order, WatchTheme.id).all()
    return [{"id": t.id, "name": t.name, "description": t.description} for t in themes_raw]


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
        themes_data = load_active_weekly_themes(session, theme_ids=theme_ids)
        logger.info(f"Loaded {len(themes_data)} active watch themes (scope weekly/both) "
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
