#!/usr/bin/env python3
"""Weekly "research desk" web-research injector (Paul 2026-07-10).

Searches the web for AI standards / governance / industry-consortium news
(audience: standards-body and consortium professionals — FIDO Alliance,
USB-IF, PCI-SIG class organizations), triages candidates with an LLM judge,
and injects genuinely interesting hits as pre-scored text "episodes" so the
nightly digest pipeline covers them like any other source. The pipeline
itself needs no changes — this uses the existing Episode/Feed seams:

  - One-time pseudo-feed (feed_url="harold://web-research", active=False so
    RSS discovery never touches it).
  - Per-article Episode rows with status="scored" and
    scores={"AI and Technology": 0.9} so get_scored_episodes_for_topic()
    picks them up like any transcribed episode.

Run manually or via cron (recommended: Monday 06:30 PT, see
scripts/run_research_desk.sh). Idempotency: episode_guid is a deterministic
hash of the source URL (DB-level dedupe via get_or_create) AND a persistent
append-only ledger at data/research_desk_ledger.json (survives retention
purging the episode row after 14 days — see retention_manager.py).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

# Allow running as a script from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parent.parent / '.env')

import httpx  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402
from openai import OpenAI  # noqa: E402

from src.database.episode_status import EpisodeStatus  # noqa: E402
from src.database.models import (  # noqa: E402
    DatabaseManager, Episode, Feed, get_database_manager, get_episode_repo, get_feed_repo,
)

logger = logging.getLogger("research_desk")

# ---------------------------------------------------------------------------
# Constants — the injection recipe (verified against src/database/models.py,
# src/publishing/retention_manager.py, src/generation/script_generator.py,
# src/audio/metadata_generator.py; see kanban context in the launching
# message for exact line references).
# ---------------------------------------------------------------------------

PSEUDO_FEED_URL = "harold://web-research"
PSEUDO_FEED_TITLE = "Harold Web Research"

# Must match config/topics.json topic "name" exactly — near-miss keys score
# zero (src/database/models.py get_scored_episodes_for_topic).
TOPIC_NAME = "AI and Technology"
TOPIC_SCORE = 0.9

# Matches script_generator.py's MIN_DIGEST_TRANSCRIPT_CHARS gate — anything
# shorter never qualifies for a digest, so there's no point injecting it.
MIN_TRANSCRIPT_CHARS = 1000

TRIAGE_THRESHOLD = 0.7
DEFAULT_MAX_INJECT = 2
DEFAULT_MODEL = "gpt-5.2"

DEFAULT_LEDGER_PATH = Path(__file__).resolve().parent.parent / "data" / "research_desk_ledger.json"

# Configurable query angles — (short label, search instruction). Edit this
# list to retarget the desk; everything downstream is angle-agnostic.
QUERY_ANGLES: List[Tuple[str, str]] = [
    ("new-standards", "New AI standards or technical specification releases"),
    ("consortium-formation", "AI industry consortium or alliance formation and new member "
                              "organization announcements"),
    ("working-group-output", "AI working-group output or draft specifications from bodies such "
                              "as W3C, ISO/IEC, IEEE, the Linux Foundation, or MLCommons"),
    ("interoperability", "AI interoperability or protocol standardization news, including "
                          "agent-to-agent or tool-use protocols"),
    ("governance-frameworks", "AI governance framework announcements developed with "
                               "cross-industry consortium participation"),
]

SEARCH_SYSTEM_PROMPT = """\
You are a research analyst producing a weekly briefing for standards-body and \
industry-consortium professionals — the audience resembles staff at \
organizations like FIDO Alliance, USB-IF, or PCI-SIG. Use the web_search tool \
to find genuine, recent news matching the requested angle, restricted to \
items published in the last 7 days. Only include real articles you actually \
found via search — never invent a URL, publication, or date. If nothing \
genuinely relevant turns up, return an empty candidates array rather than \
padding with weak matches."""

SEARCH_TEXT_FORMAT = {
    "type": "json_schema",
    "name": "ResearchCandidates",
    "schema": {
        "type": "object",
        "properties": {
            "candidates": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "url": {"type": "string"},
                        "publication": {"type": "string"},
                        "author": {"type": ["string", "null"]},
                        "published_date": {"type": "string"},
                        "summary": {"type": "string"},
                    },
                    "required": ["title", "url", "publication", "author", "published_date", "summary"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["candidates"],
        "additionalProperties": False,
    },
    "strict": True,
}

TRIAGE_SYSTEM_PROMPT = """\
You are triaging article candidates for a weekly research desk aimed at \
standards-body and industry-consortium professionals (audience resembles \
FIDO Alliance, USB-IF, PCI-SIG staff). Score how genuinely interesting this \
candidate is as cross-industry AI collaboration/standards news for that \
audience, from 0.0 (not relevant / low quality) to 1.0 (highly relevant, \
must-cover). Give one concise sentence of rationale."""

TRIAGE_TEXT_FORMAT = {
    "type": "json_schema",
    "name": "TriageVerdict",
    "schema": {
        "type": "object",
        "properties": {
            "score": {"type": "number"},
            "rationale": {"type": "string"},
        },
        "required": ["score", "rationale"],
        "additionalProperties": False,
    },
    "strict": True,
}


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    title: str
    url: str
    publication: str
    author: Optional[str]
    published_date: str
    summary: str
    query_angle: str


@dataclass
class TriageVerdict:
    score: float
    rationale: str


@dataclass
class RunStats:
    searched: int = 0
    triaged: int = 0
    qualified: int = 0
    injected: int = 0
    skipped: List[Tuple[str, str]] = field(default_factory=list)
    fatal: bool = False


# ---------------------------------------------------------------------------
# Model helpers
# ---------------------------------------------------------------------------

def get_reasoning_effort(model: str) -> str:
    """GPT-5.2* models only support 'medium' reasoning effort (matches
    src/scoring/content_scorer.py::_get_reasoning_effort)."""
    if model.startswith("gpt-5.2"):
        return "medium"
    return "minimal"


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def search_web(client, model: str, angle_label: str, angle_query: str):
    """Thin wrapper around the Responses API web_search call. Isolated so
    tests can substitute a mock client without touching parsing logic."""
    return client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": SEARCH_SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"Query angle: {angle_label}\n\n{angle_query}\n\n"
                "Return up to 5 candidate articles published in the last 7 days."
            )},
        ],
        tools=[{"type": "web_search", "search_context_size": "medium"}],
        reasoning={"effort": get_reasoning_effort(model)},
        max_output_tokens=4000,
        text={"format": SEARCH_TEXT_FORMAT},
    )


def _strip_code_fence(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return raw


def parse_candidates(response, angle_label: str) -> List[Candidate]:
    """Parse a search_web() response into Candidate objects. Pure function —
    takes anything with an .output_text attribute, so tests can pass a
    SimpleNamespace instead of a real OpenAI Response."""
    raw = getattr(response, "output_text", None)
    if not raw:
        return []
    raw = _strip_code_fence(raw)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning(f"Non-JSON search response for angle '{angle_label}': {e}")
        return []

    items = parsed.get("candidates", []) if isinstance(parsed, dict) else []
    candidates: List[Candidate] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        url = (item.get("url") or "").strip()
        title = (item.get("title") or "").strip()
        if not url or not title:
            continue
        candidates.append(Candidate(
            title=title,
            url=url,
            publication=(item.get("publication") or "Unknown publication").strip(),
            author=(item.get("author") or None),
            published_date=(item.get("published_date") or "an unspecified date").strip(),
            summary=(item.get("summary") or "").strip(),
            query_angle=angle_label,
        ))
    return candidates


# ---------------------------------------------------------------------------
# Triage
# ---------------------------------------------------------------------------

def triage_candidate(client, model: str, candidate: Candidate) -> TriageVerdict:
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": TRIAGE_SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"Title: {candidate.title}\n"
                f"Publication: {candidate.publication}\n"
                f"URL: {candidate.url}\n"
                f"Summary: {candidate.summary}\n"
            )},
        ],
        reasoning={"effort": get_reasoning_effort(model)},
        max_output_tokens=500,
        text={"format": TRIAGE_TEXT_FORMAT},
    )
    raw = _strip_code_fence(response.output_text)
    parsed = json.loads(raw)
    return TriageVerdict(score=float(parsed["score"]), rationale=str(parsed["rationale"]).strip())


# ---------------------------------------------------------------------------
# Article fetch + extraction
# ---------------------------------------------------------------------------

def fetch_article_text(url: str, timeout: float = 15.0) -> Optional[str]:
    try:
        resp = httpx.get(
            url, timeout=timeout, follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; HaroldResearchDesk/1.0)"},
        )
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"Fetch failed for {url}: {e}")
        return None
    return extract_main_text(resp.text)


def extract_main_text(html_content: str) -> str:
    """Heuristic main-text extraction: prefer <article>/<main>, fall back to
    the whole body, strip chrome, join paragraph text."""
    soup = BeautifulSoup(html_content, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form", "noscript"]):
        tag.decompose()
    container = soup.find("article") or soup.find("main") or soup.body or soup
    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p")]
    text = "\n\n".join(p for p in paragraphs if p)
    return text.strip()


def pad_summary(candidate: Candidate) -> str:
    """Fallback body when full-text extraction comes up short: the search
    result's own summary padded with metadata, used ONLY if it still clears
    MIN_TRANSCRIPT_CHARS."""
    parts = [
        candidate.summary,
        "",
        f"Additional context: surfaced via a research-desk web search for "
        f'"{candidate.query_angle}". Publication: {candidate.publication}. '
        f"Headline: {candidate.title}. Reported date: {candidate.published_date}. "
        f"Source URL: {candidate.url}.",
    ]
    return "\n".join(parts).strip()


# ---------------------------------------------------------------------------
# Injection
# ---------------------------------------------------------------------------

def build_episode_guid(url: str) -> str:
    return f"harold-web-research-{hashlib.sha1(url.encode('utf-8')).hexdigest()[:16]}"


def build_transcript(candidate: Candidate, body: str) -> str:
    """Header line + blank line + body, per the injection recipe. The header
    is a citation line, not a caption — it must stay factual."""
    author_part = f"by {candidate.author}, " if candidate.author else ""
    header = (
        f"Written article from {candidate.publication}, {author_part}"
        f"published {candidate.published_date}. {candidate.url}"
    )
    return f"{header}\n\n{body}"


def ensure_pseudo_feed(feed_repo) -> int:
    """Get-or-create the inactive pseudo-feed. Inactive feeds are never
    fetched by RSS discovery (src/database/models.py get_active_feeds)."""
    existing = feed_repo.get_by_url(PSEUDO_FEED_URL)
    if existing:
        return existing.id
    return feed_repo.create(Feed(feed_url=PSEUDO_FEED_URL, title=PSEUDO_FEED_TITLE, active=False))


def inject_candidate(episode_repo, feed_id: int, candidate: Candidate, transcript_content: str) -> Tuple[int, bool]:
    now = datetime.now()
    episode = Episode(
        episode_guid=build_episode_guid(candidate.url),
        feed_id=feed_id,
        title=f"{candidate.title} — {candidate.publication}",
        published_date=now,  # NEVER backdate — retention deletes on published_date < now-14d
        audio_url=candidate.url,
        transcript_content=transcript_content,
        transcript_word_count=len(transcript_content.split()),
        transcript_generated_at=now,
        scores={TOPIC_NAME: TOPIC_SCORE},
        scored_at=now,
        status=EpisodeStatus.SCORED.value,
    )
    return episode_repo.get_or_create(episode)


# ---------------------------------------------------------------------------
# Ledger (persistent dedupe across retention purges)
# ---------------------------------------------------------------------------

def load_ledger(path: Path) -> List[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Ledger at {path} unreadable ({e}); treating as empty")
        return []


def ledger_urls(entries: List[dict]) -> set:
    return {e.get("url") for e in entries if e.get("url")}


def append_ledger(path: Path, entry: dict) -> None:
    entries = load_ledger(path)
    entries.append(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2))


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _print_dry_run(judged: List[Tuple[Candidate, TriageVerdict]], top: List[Tuple[Candidate, TriageVerdict]]) -> None:
    print(f"\n=== DRY RUN: {len(judged)} candidates triaged, {len(top)} would be injected ===\n")
    for candidate, verdict in judged:
        marker = "SELECTED" if (candidate, verdict) in top else "skipped"
        print(f"[{marker}] score={verdict.score:.2f} — {candidate.title} ({candidate.publication})")
        print(f"    {candidate.url}")
        print(f"    rationale: {verdict.rationale}")
    print()


def _log_summary(stats: RunStats) -> None:
    logger.info(
        f"Research desk summary: searched={stats.searched} triaged={stats.triaged} "
        f"qualified={stats.qualified} injected={stats.injected} skipped={len(stats.skipped)}"
    )
    for title, reason in stats.skipped:
        logger.info(f"  skipped: {title!r} — {reason}")


def run(
    *,
    db_manager: Optional[DatabaseManager] = None,
    client=None,
    model: str = DEFAULT_MODEL,
    max_inject: int = DEFAULT_MAX_INJECT,
    dry_run: bool = False,
    ledger_path: Path = DEFAULT_LEDGER_PATH,
    angles: Optional[List[Tuple[str, str]]] = None,
) -> RunStats:
    angles = QUERY_ANGLES if angles is None else angles
    stats = RunStats()

    ledger_entries = load_ledger(ledger_path)
    seen_urls = ledger_urls(ledger_entries)

    # --- search ---
    all_candidates: List[Candidate] = []
    search_failures = 0
    for label, query in angles:
        try:
            response = search_web(client, model, label, query)
        except Exception as e:
            logger.error(f"Search failed for angle '{label}': {e}")
            search_failures += 1
            continue
        found = parse_candidates(response, label)
        stats.searched += len(found)
        all_candidates.extend(found)

    if angles and search_failures == len(angles):
        logger.error(
            f"All {len(angles)} search angles failed against model '{model}'. "
            "Verify OPENAI_API_KEY and that the model supports the web_search "
            "tool. Aborting run without injecting anything."
        )
        stats.fatal = True
        return stats

    # --- dedupe against the ledger (before spending judge calls) ---
    fresh: List[Candidate] = []
    seen_this_run: set = set()
    for c in all_candidates:
        if c.url in seen_urls or c.url in seen_this_run:
            stats.skipped.append((c.title, "already in ledger"))
            continue
        seen_this_run.add(c.url)
        fresh.append(c)

    # --- triage ---
    judged: List[Tuple[Candidate, TriageVerdict]] = []
    for c in fresh:
        try:
            verdict = triage_candidate(client, model, c)
        except Exception as e:
            logger.warning(f"Triage failed for '{c.title}': {e}")
            stats.skipped.append((c.title, f"triage error: {e}"))
            continue
        stats.triaged += 1
        judged.append((c, verdict))
        if verdict.score >= TRIAGE_THRESHOLD:
            stats.qualified += 1

    qualifying = [(c, v) for c, v in judged if v.score >= TRIAGE_THRESHOLD]
    qualifying.sort(key=lambda cv: cv[1].score, reverse=True)
    top = qualifying[:max_inject]

    if dry_run:
        _print_dry_run(judged, top)

    feed_id = None
    episode_repo = None
    if not dry_run:
        feed_repo = get_feed_repo(db_manager)
        episode_repo = get_episode_repo(db_manager)
        feed_id = ensure_pseudo_feed(feed_repo)

    for candidate, verdict in top:
        body = fetch_article_text(candidate.url)
        source = "full-article"
        if not body or len(body) < MIN_TRANSCRIPT_CHARS:
            padded = pad_summary(candidate)
            if len(padded) >= MIN_TRANSCRIPT_CHARS:
                body = padded
                source = "summary-fallback"
            else:
                stats.skipped.append((candidate.title, "article text and padded summary both under 1000 chars"))
                continue

        transcript = build_transcript(candidate, body)

        if dry_run:
            print(f"--- DRY RUN transcript preview: {candidate.title} ({source}, "
                  f"{len(transcript)} chars) ---")
            print(transcript[:2000])
            print()
            stats.injected += 1
            continue

        episode_id, created = inject_candidate(episode_repo, feed_id, candidate, transcript)
        if created:
            stats.injected += 1
            append_ledger(ledger_path, {
                "url": candidate.url,
                "guid": build_episode_guid(candidate.url),
                "injected_at": datetime.now(timezone.utc).isoformat(),
                "title": candidate.title,
            })
            logger.info(f"Injected episode {episode_id} ({source}): {candidate.title}")
        else:
            stats.skipped.append((candidate.title, "episode_guid already existed (DB-level dedupe)"))

    _log_summary(stats)
    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    parser = argparse.ArgumentParser(
        description="Weekly AI standards/governance research desk: search, triage, and "
                    "inject genuinely interesting hits as pre-scored text episodes."
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print candidates and verdicts; insert nothing")
    parser.add_argument("--max-inject", type=int, default=DEFAULT_MAX_INJECT,
                        help=f"Maximum articles to inject per run (default {DEFAULT_MAX_INJECT})")
    parser.add_argument("--model", default=os.getenv("RESEARCH_DESK_MODEL", DEFAULT_MODEL),
                        help=f"Search-capable OpenAI model (default {DEFAULT_MODEL})")
    args = parser.parse_args(argv)

    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY not set; cannot run research desk search")
        return 1

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    db_manager = get_database_manager()

    stats = run(db_manager=db_manager, client=client, model=args.model,
                max_inject=args.max_inject, dry_run=args.dry_run)
    return 1 if stats.fatal else 0


if __name__ == "__main__":
    sys.exit(main())
