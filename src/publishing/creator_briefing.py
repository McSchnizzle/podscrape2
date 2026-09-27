"""Creator briefing email (Phase 8).

After the nightly digest publishes, email a short, readable rundown of the
day's key stories to a creator who makes his own daily AI news videos. The
podcast is for listening; this is for someone who is about to go research and
record, so every story carries links out and questions worth chasing.

Three things here are deliberate:

- Links are never invented. The drafting call uses the Responses API
  ``web_search`` tool, and a source link survives only if its URL appeared in
  what the search actually returned or opened, AND it answers a live request.
  Every story also gets search links (news + YouTube) that cannot be dead.
- Recipients live in ``web_settings`` (category ``creator_briefing``), never in
  source. This repo is public.
- A digest is sent to a recipient at most once (``briefing_email_sends``);
  previews are recorded with ``is_test`` and never block the real send.
"""
from __future__ import annotations

import html
import json
import logging
import os
import re
import smtplib
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, make_msgid
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import quote_plus, urlsplit

import httpx

logger = logging.getLogger(__name__)

SENDER_ADDRESS = "paulinpdx503@gmail.com"
SENDER_NAME = "Harold at Paul's AI News Desk"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# Only digests this recent are candidates, so a pipeline that was down for a
# week does not wake up and mail stale news.
MAX_DIGEST_AGE_DAYS = 2
SCRIPT_CHAR_BUDGET = 30000
LINK_CHECK_TIMEOUT = 10.0
MAX_REDIRECTS = 5
LINK_CHECK_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0 Safari/537.36"
)
# Sites that exist but refuse bots answer 401/403/429. The URL itself came from
# a real search result, so those count as alive; 404/410/5xx/DNS do not.
BOT_BLOCK_STATUSES = {401, 403, 429}

# Email clients ignore CSS custom properties, so the house tokens are resolved
# here, once, from ~/.claude/design/tokens.css (LIGHT "Warm Cream / Forest").
# Templates reference these names only; no raw colors below this block.
TOKENS = {
    "bg": "#f3efe7",
    "surface_1": "#ffffff",
    "surface_2": "#faf7f0",
    "surface_3": "#f0ebe0",
    "border": "#e3ddcf",
    "border_strong": "#cdc5b3",
    "text": "#15201c",
    "text_muted": "#3a4641",
    "text_subtle": "#6b756f",
    "accent": "#1f4d40",
    "accent_hover": "#25584a",
    "accent_soft": "#e5efe9",
    "on_accent": "#f5f1e8",
    "warm": "#b8722f",
    "warm_soft": "#f5e8d6",
    "success": "#2f8f6e",
    "warning": "#b67d22",
    "font_serif": "'Source Serif 4', Georgia, 'Times New Roman', serif",
    "font_sans": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif",
    "shadow_sm": "0 6px 24px rgba(21,32,28,0.08)",
    "radius": "12px",
    "radius_sm": "7px",
    "radius_full": "999px",
}


class BriefingError(Exception):
    """A configuration or generation failure that must fail the phase."""


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@dataclass
class BriefingSettings:
    enabled: bool
    recipients: List[str]
    recipient_name: str
    model: str
    max_stories: int

    @classmethod
    def load(cls) -> "BriefingSettings":
        from src.config.web_config import WebConfigManager, SettingsKeys, DEFAULTS
        keys = SettingsKeys.CreatorBriefing
        wc = WebConfigManager()

        def get(key):
            return wc.get_setting(keys.CATEGORY, key, DEFAULTS[(keys.CATEGORY, key)]["default"])

        return cls(
            enabled=bool(get(keys.ENABLED)),
            recipients=parse_recipients(get(keys.RECIPIENTS)),
            recipient_name=str(get(keys.RECIPIENT_NAME) or "").strip(),
            model=str(get(keys.MODEL)),
            max_stories=int(get(keys.MAX_STORIES)),
        )


def parse_recipients(raw: Any) -> List[str]:
    if not raw:
        return []
    out = []
    for part in str(raw).replace(";", ",").split(","):
        addr = part.strip()
        if not addr:
            continue
        if "@" not in addr or " " in addr:
            raise BriefingError(f"creator_briefing.recipients has a malformed address: {addr!r}")
        out.append(addr)
    return out


# ---------------------------------------------------------------------------
# Material
# ---------------------------------------------------------------------------

@dataclass
class SourceEpisode:
    show: str
    title: str
    url: str

    @property
    def is_video(self) -> bool:
        host = (urlsplit(self.url).hostname or "").lower()
        return host.endswith("youtube.com") or host.endswith("youtu.be")


@dataclass
class BriefingMaterial:
    digest_id: int
    digest_date: date
    episode_title: str
    episode_summary: str
    release_url: Optional[str]
    script: str
    arcs: List[Dict[str, str]]
    episodes: List[SourceEpisode]


def select_digest(session, today: date):
    """Newest published digest no older than MAX_DIGEST_AGE_DAYS."""
    from src.database.sqlalchemy_models import Digest
    cutoff = today - timedelta(days=MAX_DIGEST_AGE_DAYS)
    return (
        session.query(Digest)
        .filter(Digest.status == "published")
        .filter(Digest.github_url.isnot(None))
        .filter(Digest.digest_date >= cutoff)
        .order_by(Digest.digest_date.desc(), Digest.id.desc())
        .first()
    )


def gather_material(session, digest) -> BriefingMaterial:
    from src.database.sqlalchemy_models import (
        DigestEpisodeLink, Episode, Feed, StoryArc, StoryArcCoverage,
    )

    arcs = []
    coverage = session.query(StoryArcCoverage).filter_by(digest_id=digest.id).all()
    for cov in coverage:
        arc = session.get(StoryArc, cov.story_arc_id)
        if arc is None:
            continue
        latest = max(arc.events, key=lambda e: e.event_date) if arc.events else None
        arcs.append({
            "name": arc.arc_name,
            "category": arc.functional_category,
            "latest": (latest.event_summary if latest else arc.summary) or "",
        })

    episodes = []
    links = (
        session.query(DigestEpisodeLink)
        .filter_by(digest_id=digest.id)
        .order_by(DigestEpisodeLink.position.asc().nullslast(), DigestEpisodeLink.id)
        .all()
    )
    for link in links:
        ep = session.get(Episode, link.episode_id)
        if ep is None:
            continue
        feed = session.get(Feed, ep.feed_id)
        url = ep.audio_url if ep.audio_url and ep.audio_url.startswith("https://") else ""
        episodes.append(SourceEpisode(show=feed.title if feed else "Unknown show", title=ep.title, url=url))

    # mp3_summary carries a "Source episodes:" list for the podcast feed; the
    # structured episode list above replaces it here.
    summary = (digest.mp3_summary or "").split("Source episodes:")[0].strip()

    return BriefingMaterial(
        digest_id=digest.id,
        digest_date=digest.digest_date,
        episode_title=digest.mp3_title or f"AI and Technology, {digest.digest_date}",
        episode_summary=summary,
        release_url=digest.github_url,
        script=(digest.script_content or "")[:SCRIPT_CHAR_BUDGET],
        arcs=arcs,
        episodes=episodes,
    )


# ---------------------------------------------------------------------------
# Drafting
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You write a nightly email for {reader}, a young creator who makes his own \
daily AI news YouTube video. It is sent by Harold, Paul's AI assistant, from the stories \
Paul's podcast pipeline covered tonight. Paul is family and set this up for him.

The reader should finish the email knowing what happened, which stories are worth a video, \
and where to start digging. He does his own research and forms his own takes; your job \
is to hand him good starting points and good questions, never a finished script.

Voice: fun, quick, a little irreverent, like a sharp friend who reads everything. Short \
paragraphs. Concrete numbers and names over adjectives. Jokes are welcome when they \
land; never cringe, never corporate, never talk down to him. Write about Paul in the \
third person; Harold never pretends to be Paul.

Use the web_search tool. For each story, find the original reporting or primary source \
(the company announcement, the paper, the filing, a solid news outlet). Only put URLs in \
"sources" that you actually saw in search results or opened. If you cannot corroborate \
a claim beyond the podcasts, mark the story "single_source" and say so plainly in \
what_happened; that is useful information for someone about to say it on camera.

Keep it skimmable: he should get through the whole email in about three minutes. \
Respect the word limits in the schema. Never put URLs, markdown links, or citations in \
any prose field; links belong only in "sources". Do not use em dashes. Do not sign the \
sign_off; the signature is added for you.

Pick the stories a daily AI news channel would most want, strongest first. Merge \
duplicates. Skip sponsor reads and filler. "heard_on" lists the numbers of the source \
episodes the story came from.

{banned}"""

USER_TEMPLATE = """Tonight's podcast episode: {title}
Summary: {summary}

STORY ARCS COVERED TONIGHT
{arcs}

SOURCE EPISODES (numbered)
{episodes}

TONIGHT'S PODCAST SCRIPT (what the hosts actually said)
{script}

Write the email content for {count_phrase} stories."""

STORY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["kicker", "headline", "what_happened", "why_it_matters", "video_angle",
                 "dig_deeper", "news_search_query", "confidence", "heard_on", "sources"],
    "properties": {
        "kicker": {"type": "string", "description": "2-3 word uppercase-able label, e.g. MODEL WARS"},
        "headline": {"type": "string", "description": "Punchy headline, under 70 characters"},
        "what_happened": {"type": "string", "description": "The facts: at most 3 sentences and 60 words, one paragraph"},
        "why_it_matters": {"type": "string", "description": "Why people care: at most 2 sentences and 35 words, one paragraph"},
        "video_angle": {"type": "string", "description": "One hook or angle for a video segment, under 40 words"},
        "dig_deeper": {"type": "array", "items": {"type": "string"},
                       "description": "2 open questions worth researching, each under 25 words; he answers them, not you"},
        "news_search_query": {"type": "string", "description": "A good news search query to start research"},
        "confidence": {"type": "string", "enum": ["confirmed", "single_source"]},
        "heard_on": {"type": "array", "items": {"type": "integer"}},
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "publication", "url"],
                "properties": {
                    "title": {"type": "string"},
                    "publication": {"type": "string"},
                    "url": {"type": "string"},
                },
            },
        },
    },
}

DRAFT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["subject", "opener", "stories", "rabbit_hole", "sign_off"],
    "properties": {
        "subject": {"type": "string", "description": "Email subject, under 80 characters, names the top story"},
        "opener": {"type": "string", "description": "Hello that sets up tonight: at most 3 sentences and 50 words"},
        "stories": {"type": "array", "items": STORY_SCHEMA},
        "rabbit_hole": {
            "type": "object",
            "additionalProperties": False,
            "required": ["title", "blurb", "search_query"],
            "properties": {
                "title": {"type": "string"},
                "blurb": {"type": "string", "description": "One weird, delightful, or nerdy thread worth an evening, under 60 words"},
                "search_query": {"type": "string"},
            },
        },
        "sign_off": {"type": "string", "description": "One-line send-off, no name or signature"},
    },
}


def build_prompt(material: BriefingMaterial, max_stories: int, reader: str = "") -> Tuple[str, str]:
    from src.generation.anti_ai_rules import compact_banned_list
    arcs = "\n".join(f"- [{a['category']}] {a['name']}: {a['latest']}" for a in material.arcs) or "- (none recorded)"
    episodes = "\n".join(
        f"{i}. {e.show}: {e.title}" for i, e in enumerate(material.episodes, start=1)
    ) or "(none recorded)"
    low = max(3, max_stories - 1)
    count_phrase = f"{low} to {max_stories}" if low < max_stories else str(max_stories)
    system = SYSTEM_PROMPT.format(reader=reader or "the reader", banned=compact_banned_list())
    user = USER_TEMPLATE.format(
        title=material.episode_title, summary=material.episode_summary or "(none)",
        arcs=arcs, episodes=episodes, script=material.script or "(script unavailable)",
        count_phrase=count_phrase,
    )
    return system, user


def draft_briefing(client, model: str, material: BriefingMaterial, max_stories: int,
                   reader: str = "") -> Tuple[Dict[str, Any], Set[str]]:
    """Returns (draft, urls the web search actually surfaced)."""
    from src.config.models import reasoning_effort
    system, user = build_prompt(material, max_stories, reader)
    response = client.responses.create(
        model=model,
        input=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        tools=[{"type": "web_search", "search_context_size": "medium"}],
        include=["web_search_call.action.sources"],
        reasoning={"effort": reasoning_effort("briefing", model)},
        max_output_tokens=32000,
        text={"format": {"type": "json_schema", "name": "creator_briefing", "strict": True,
                         "schema": DRAFT_SCHEMA}},
    )
    raw = getattr(response, "output_text", "") or ""
    if not raw.strip():
        raise BriefingError(f"{model} returned no text (status={getattr(response, 'status', '?')})")
    try:
        draft = json.loads(raw)
    except json.JSONDecodeError as e:
        raise BriefingError(f"{model} returned non-JSON briefing: {e}") from e
    if not draft.get("stories"):
        raise BriefingError(f"{model} returned a briefing with no stories")
    return clean_draft(draft), surfaced_urls(response)


# web_search appends "([site](url))" citations to prose even when told not to.
# Those URLs never pass verify_sources(), so they must not reach the email.
_CITATION = re.compile(r"\s*\(\[[^\]]*\]\([^)]*\)\)")
_MD_LINK = re.compile(r"\[([^\]]+)\]\((?:https?://)[^)]*\)")
_BARE_URL = re.compile(r"\s*\(?https?://[^\s)]*[^\s).,;:!?]\)?")
_EM_DASH = re.compile(r"\s*\u2014\s*")
_TRAILING_SIGNATURE = re.compile(r"[\s,\-\u2013\u2014]*(?:love,?\s*)?harold\W*$", re.IGNORECASE)


def clean_prose(text: str) -> str:
    text = _CITATION.sub("", text or "")
    text = _MD_LINK.sub(r"\1", text)
    text = _BARE_URL.sub("", text)
    text = _EM_DASH.sub(", ", text)
    text = re.sub(r"\s*\n\s*\n\s*", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    return text.strip()


def clean_draft(draft: Dict[str, Any]) -> Dict[str, Any]:
    for key in ("subject", "opener", "sign_off"):
        draft[key] = clean_prose(draft.get(key, ""))
    draft["sign_off"] = _TRAILING_SIGNATURE.sub("", draft["sign_off"]).strip() or "See you tomorrow."
    rh = draft.get("rabbit_hole") or {}
    for key in ("title", "blurb"):
        rh[key] = clean_prose(rh.get(key, ""))
    for story in draft.get("stories", []):
        for key in ("kicker", "headline", "what_happened", "why_it_matters", "video_angle"):
            story[key] = clean_prose(story.get(key, ""))
        story["dig_deeper"] = [clean_prose(q) for q in story.get("dig_deeper", []) if clean_prose(q)]
    return draft


def surfaced_urls(response) -> Set[str]:
    """Every URL the web_search tool returned or opened, normalized."""
    from scripts.research_desk import normalize_url
    urls: Set[str] = set()
    for item in getattr(response, "output", None) or []:
        if getattr(item, "type", None) == "web_search_call":
            action = getattr(item, "action", None)
            for src in getattr(action, "sources", None) or []:
                if getattr(src, "url", None):
                    urls.add(normalize_url(src.url))
            if getattr(action, "url", None):
                urls.add(normalize_url(action.url))
        elif getattr(item, "type", None) == "message":
            for part in getattr(item, "content", None) or []:
                for ann in getattr(part, "annotations", None) or []:
                    if getattr(ann, "url", None):
                        urls.add(normalize_url(ann.url))
    return urls


# ---------------------------------------------------------------------------
# Link verification
# ---------------------------------------------------------------------------

def check_link(url: str, timeout: float = LINK_CHECK_TIMEOUT) -> Tuple[bool, str]:
    """True if the URL answers. https only, and every hop is resolved and
    pinned to a vetted public address (the research desk's SSRF guard)."""
    from scripts.research_desk import UnsafeUrlError, _require_https_host, _resolve_and_pin
    current = url
    try:
        with httpx.Client(follow_redirects=False, timeout=timeout,
                          headers={"User-Agent": LINK_CHECK_USER_AGENT}) as client:
            for _ in range(MAX_REDIRECTS + 1):
                host = _require_https_host(current)
                pinned_ip = _resolve_and_pin(host)[0]
                parsed = urlsplit(current)
                request = client.build_request(
                    "GET", httpx.URL(current).copy_with(host=pinned_ip),
                    headers={"Host": host if not parsed.port else f"{host}:{parsed.port}"},
                    extensions={"sni_hostname": host},
                )
                resp = client.send(request, stream=True)
                try:
                    if resp.is_redirect and resp.headers.get("location"):
                        current = str(httpx.URL(current).join(resp.headers["location"]))
                        continue
                    status = resp.status_code
                finally:
                    resp.close()
                if status < 400 or status in BOT_BLOCK_STATUSES:
                    return True, f"HTTP {status}"
                return False, f"HTTP {status}"
            return False, "too many redirects"
    except UnsafeUrlError as e:
        return False, f"unsafe: {e}"
    except httpx.HTTPError as e:
        return False, f"{type(e).__name__}: {e}"


@dataclass
class LinkReport:
    kept: int = 0
    dropped: List[Tuple[str, str]] = field(default_factory=list)


def verify_sources(draft: Dict[str, Any], surfaced: Set[str], checker=check_link) -> LinkReport:
    """Drop any source link the search did not surface or that is dead."""
    from scripts.research_desk import normalize_url
    report = LinkReport()
    for story in draft.get("stories", []):
        kept = []
        seen = set()
        for src in story.get("sources", []):
            url = (src.get("url") or "").strip()
            try:
                norm = normalize_url(url)
            except Exception:
                report.dropped.append((url, "unparseable"))
                continue
            if norm in seen:
                continue
            if norm not in surfaced:
                report.dropped.append((url, "not in search results"))
                continue
            ok, why = checker(norm)
            if not ok:
                report.dropped.append((url, why))
                continue
            seen.add(norm)
            kept.append({**src, "url": norm})
        story["sources"] = kept[:3]
        report.kept += len(story["sources"])
    return report


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def news_search_url(query: str) -> str:
    return f"https://news.google.com/search?q={quote_plus(query)}"


def youtube_search_url(query: str) -> str:
    return f"https://www.youtube.com/results?search_query={quote_plus(query)}"


def _e(text: Any) -> str:
    return html.escape(str(text or ""), quote=True)


def _p(text: Any) -> str:
    """Escaped prose with paragraph breaks preserved."""
    return "<br><br>".join(_e(part) for part in str(text or "").split("\n\n"))


def _safe_href(url: str) -> str:
    return _e(url) if url.startswith("https://") else ""


def _heard_on(story: Dict[str, Any], material: BriefingMaterial) -> List[SourceEpisode]:
    out = []
    for n in story.get("heard_on", []):
        if isinstance(n, int) and 1 <= n <= len(material.episodes):
            ep = material.episodes[n - 1]
            if ep not in out:
                out.append(ep)
    return out


def _date_label(d: date) -> str:
    return f"{d.strftime('%A, %B')} {d.day}"


def desk_name(reader: str) -> str:
    return f"{reader}'s AI Desk" if reader else "The AI Desk"


def render_html(draft: Dict[str, Any], material: BriefingMaterial, preview: bool = False,
                reader: str = "") -> str:
    t = TOKENS
    link = f"color:{t['accent']};font-weight:600;text-decoration:underline;"
    stories = draft["stories"]

    glance = "".join(
        f'<tr><td style="padding:6px 0;font:600 15px/1.45 {t["font_sans"]};color:{t["text"]};">'
        f'<span style="display:inline-block;min-width:26px;color:{t["warm"]};font-weight:700;">{i}</span>'
        f'<a href="#s{i}" style="color:{t["text"]};text-decoration:none;">{_e(s["headline"])}</a></td></tr>'
        for i, s in enumerate(stories, start=1)
    )

    cards = []
    for i, s in enumerate(stories, start=1):
        badge_color, badge_label = (
            (t["success"], "Confirmed in the press") if s.get("confidence") == "confirmed"
            else (t["warning"], "Podcast chatter only, verify first")
        )
        sources = "".join(
            f'<li style="margin:0 0 6px;"><a href="{_safe_href(src["url"])}" style="{link}">{_e(src["title"])}</a>'
            f' <span style="color:{t["text_subtle"]};">({_e(src["publication"])})</span></li>'
            for src in s.get("sources", []) if _safe_href(src.get("url", ""))
        )
        heard = "".join(
            f'<li style="margin:0 0 6px;"><a href="{_safe_href(ep.url)}" style="{link}">{_e(ep.title)}</a>'
            f' <span style="color:{t["text_subtle"]};">({_e(ep.show)}{", video" if ep.is_video else ", audio"})</span></li>'
            if ep.url else
            f'<li style="margin:0 0 6px;color:{t["text_muted"]};">{_e(ep.title)} ({_e(ep.show)})</li>'
            for ep in _heard_on(s, material)
        )
        questions = "".join(f'<li style="margin:0 0 6px;">{_e(q)}</li>' for q in s.get("dig_deeper", []))
        q = s.get("news_search_query") or s["headline"]
        label = f'font:600 11px/1.2 {t["font_sans"]};letter-spacing:.06em;text-transform:uppercase;color:{t["text_subtle"]};margin:20px 0 8px;'
        cards.append(f"""
<tr><td style="padding:0 0 24px;">
<a name="s{i}" id="s{i}"></a>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{t['surface_1']};border:1px solid {t['border_strong']};border-radius:{t['radius']};box-shadow:{t['shadow_sm']};">
<tr><td style="padding:28px 28px 24px;">
  <div style="font:700 11px/1.2 {t['font_sans']};letter-spacing:.08em;text-transform:uppercase;color:{t['warm']};">{i:02d} &middot; {_e(s.get('kicker', ''))}</div>
  <h2 style="margin:10px 0 12px;font:600 24px/1.2 {t['font_serif']};color:{t['text']};">{_e(s['headline'])}</h2>
  <div style="display:inline-block;padding:4px 10px;border-radius:{t['radius_full']};border:1px solid {badge_color};color:{badge_color};font:600 12px/1.2 {t['font_sans']};">{badge_label}</div>
  <p style="margin:16px 0 0;font:400 15px/1.6 {t['font_sans']};color:{t['text']};">{_p(s['what_happened'])}</p>
  <p style="margin:12px 0 0;font:400 15px/1.6 {t['font_sans']};color:{t['text_muted']};"><strong style="color:{t['text']};">Why people care:</strong> {_p(s['why_it_matters'])}</p>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:18px 0 0;background:{t['warm_soft']};border-left:4px solid {t['warm']};border-radius:{t['radius_sm']};">
    <tr><td style="padding:14px 16px;font:400 15px/1.55 {t['font_sans']};color:{t['text']};"><strong>Video angle:</strong> {_p(s['video_angle'])}</td></tr>
  </table>
  <div style="{label}">Your homework, if you want it</div>
  <ul style="margin:0;padding-left:20px;font:400 15px/1.55 {t['font_sans']};color:{t['text']};">{questions}</ul>
  {f'<div style="{label}">Read the source</div><ul style="margin:0;padding-left:20px;font:400 14px/1.5 {t["font_sans"]};color:{t["text"]};">{sources}</ul>' if sources else ''}
  {f'<div style="{label}">Where we heard it</div><ul style="margin:0;padding-left:20px;font:400 14px/1.5 {t["font_sans"]};color:{t["text"]};">{heard}</ul>' if heard else ''}
  <table role="presentation" cellpadding="0" cellspacing="0" style="margin:22px 0 0;"><tr>
    <td class="btn-cell" style="padding:0 8px 0 0;"><a class="btn" href="{_e(news_search_url(q))}" style="display:inline-block;padding:10px 16px;background:{t['accent']};color:{t['on_accent']};border-radius:{t['radius_sm']};font:600 14px/1 {t['font_sans']};text-decoration:none;white-space:nowrap;">Search the news</a></td>
    <td class="btn-cell"><a class="btn-ghost" href="{_e(youtube_search_url(q))}" style="display:inline-block;padding:9px 15px;border:1px solid {t['accent']};color:{t['accent']};border-radius:{t['radius_sm']};font:600 14px/1 {t['font_sans']};text-decoration:none;white-space:nowrap;">Who covered it on YouTube</a></td>
  </tr></table>
</td></tr></table>
</td></tr>""")

    rh = draft["rabbit_hole"]
    preview_banner = (
        f'<tr><td style="padding:0 0 24px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:{t["accent"]};border-radius:{t["radius"]};"><tr><td style="padding:16px 20px;'
        f'font:500 14px/1.5 {t["font_sans"]};color:{t["on_accent"]};"><strong>Preview edition.</strong> '
        f'This is a sample so you know what to expect. The real one lands every night around the time '
        f'Paul\'s podcast publishes.</td></tr></table></td></tr>'
        if preview else ""
    )
    listen = (
        f'<p style="margin:12px 0 0;font:400 14px/1.5 {t["font_sans"]};color:{t["text_muted"]};">'
        f'Rather listen? <a href="{_safe_href(material.release_url)}" style="{link}">Tonight\'s full podcast episode</a> '
        f'covers all of this with two AI hosts.</p>'
        if material.release_url and _safe_href(material.release_url) else ""
    )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><title>{_e(draft['subject'])}</title>
<style>
  a {{ transition: color 180ms cubic-bezier(0.2,0,0,1), background-color 180ms cubic-bezier(0.2,0,0,1); }}
  a:hover {{ color: {t['accent_hover']} !important; }}
  a.btn:hover {{ background: {t['accent_hover']} !important; color: {t['on_accent']} !important; }}
  a.btn-ghost:hover {{ background: {t['accent_soft']} !important; }}
  a:focus-visible {{ outline: 3px solid {t['warm']}; outline-offset: 2px; }}
  @media (max-width: 620px) {{
    .wrap {{ padding: 16px !important; }}
    .btn-cell {{ display: block !important; padding: 0 0 8px !important; }}
  }}
</style></head>
<body style="margin:0;padding:0;background:{t['bg']};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{t['bg']};">
<tr><td align="center" class="wrap" style="padding:32px 16px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;">
{preview_banner}
<tr><td style="padding:0 0 32px;">
  <div style="font:700 11px/1.2 {t['font_sans']};letter-spacing:.08em;text-transform:uppercase;color:{t['accent']};">{_e(desk_name(reader))} &middot; {_e(_date_label(material.digest_date))}</div>
  <h1 style="margin:10px 0 14px;font:700 34px/1.1 {t['font_serif']};color:{t['text']};">Tonight in AI</h1>
  <p style="margin:0;font:400 16px/1.6 {t['font_sans']};color:{t['text']};">{_p(draft['opener'])}</p>
</td></tr>
<tr><td style="padding:0 0 32px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{t['surface_3']};border:1px solid {t['border_strong']};border-radius:{t['radius']};">
  <tr><td style="padding:20px 24px;">
    <div style="font:600 11px/1.2 {t['font_sans']};letter-spacing:.06em;text-transform:uppercase;color:{t['text_subtle']};margin:0 0 10px;">At a glance</div>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{glance}</table>
  </td></tr></table>
</td></tr>
{''.join(cards)}
<tr><td style="padding:8px 0 32px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{t['surface_2']};border:1px dashed {t['warm']};border-radius:{t['radius']};">
  <tr><td style="padding:24px 28px;">
    <div style="font:700 11px/1.2 {t['font_sans']};letter-spacing:.08em;text-transform:uppercase;color:{t['warm']};">Rabbit hole of the day</div>
    <h3 style="margin:10px 0 8px;font:600 19px/1.3 {t['font_serif']};color:{t['text']};">{_e(rh['title'])}</h3>
    <p style="margin:0 0 12px;font:400 15px/1.6 {t['font_sans']};color:{t['text']};">{_p(rh['blurb'])}</p>
    <a href="{_e(news_search_url(rh['search_query']))}" style="{link}">Fall in here</a>
  </td></tr></table>
</td></tr>
<tr><td style="padding:0 0 40px;border-top:1px solid {t['border_strong']};">
  <p style="margin:24px 0 0;font:400 16px/1.6 {t['font_sans']};color:{t['text']};">{_e(draft['sign_off'])}</p>
  <p style="margin:8px 0 0;font:600 15px/1.5 {t['font_sans']};color:{t['text']};">Harold<br><span style="font-weight:400;color:{t['text_muted']};">Paul's AI assistant</span></p>
  {listen}
  <p style="margin:20px 0 0;font:400 13px/1.5 {t['font_sans']};color:{t['text_subtle']};">Harold builds this from the podcasts Paul's pipeline listened to today, then checks the web for the original reporting. AI summaries can be wrong, so read the source before you say it on camera. Just reply to this email if you want more, less, or different.</p>
</td></tr>
</table></td></tr></table></body></html>"""


def render_text(draft: Dict[str, Any], material: BriefingMaterial, preview: bool = False,
                reader: str = "") -> str:
    lines = []
    if preview:
        lines += ["PREVIEW EDITION: a sample so you know what to expect. The real one lands every night.", ""]
    lines += [f"{desk_name(reader).upper()} - {_date_label(material.digest_date)}", "", draft["opener"], "", "AT A GLANCE"]
    lines += [f"  {i}. {s['headline']}" for i, s in enumerate(draft["stories"], start=1)]
    for i, s in enumerate(draft["stories"], start=1):
        conf = "Confirmed in the press" if s.get("confidence") == "confirmed" else "Podcast chatter only, verify first"
        lines += ["", "-" * 60, f"{i}. [{s.get('kicker', '')}] {s['headline']}", f"({conf})", "",
                  s["what_happened"], "", f"Why people care: {s['why_it_matters']}", "",
                  f"Video angle: {s['video_angle']}", "", "Your homework, if you want it:"]
        lines += [f"  - {q}" for q in s.get("dig_deeper", [])]
        if s.get("sources"):
            lines.append("Read the source:")
            lines += [f"  - {src['title']} ({src['publication']}): {src['url']}" for src in s["sources"]]
        heard = _heard_on(s, material)
        if heard:
            lines.append("Where we heard it:")
            lines += [f"  - {ep.show}: {ep.title}" + (f" {ep.url}" if ep.url else "") for ep in heard]
        q = s.get("news_search_query") or s["headline"]
        lines += [f"Search the news: {news_search_url(q)}", f"Who covered it on YouTube: {youtube_search_url(q)}"]
    rh = draft["rabbit_hole"]
    lines += ["", "-" * 60, f"RABBIT HOLE OF THE DAY: {rh['title']}", rh["blurb"], news_search_url(rh["search_query"]),
              "", draft["sign_off"], "", "Harold", "Paul's AI assistant"]
    if material.release_url:
        lines += ["", f"Tonight's full podcast episode: {material.release_url}"]
    lines += ["", "Harold builds this from the podcasts Paul's pipeline listened to today, then checks the web "
              "for the original reporting. AI summaries can be wrong, so read the source before you say it on camera."]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Sending + ledger
# ---------------------------------------------------------------------------

def build_message(subject: str, html_body: str, text_body: str, recipient: str) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["From"] = formataddr((SENDER_NAME, SENDER_ADDRESS))
    msg["To"] = recipient
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain="gmail.com")
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    return msg


def send_message(msg: MIMEMultipart) -> None:
    password = os.environ.get("GMAIL_APP_PASSWORD")
    if not password:
        raise BriefingError("GMAIL_APP_PASSWORD is not set; cannot send the creator briefing")
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=60) as server:
        server.starttls()
        server.login(SENDER_ADDRESS, password)
        refused = server.send_message(msg)
    if refused:
        raise BriefingError(f"SMTP refused recipients: {refused}")


def already_sent(session, digest_id: int, recipient: str) -> bool:
    from src.database.sqlalchemy_models import BriefingEmailSend
    return session.query(BriefingEmailSend).filter_by(
        digest_id=digest_id, recipient=recipient, is_test=False,
    ).first() is not None


def record_send(session, digest_id: int, recipient: str, subject: str, message_id: str,
                story_count: int, is_test: bool) -> None:
    from src.database.sqlalchemy_models import BriefingEmailSend
    session.add(BriefingEmailSend(
        digest_id=digest_id, recipient=recipient, subject=subject, message_id=message_id,
        story_count=story_count, is_test=is_test, sent_at=datetime.now(timezone.utc),
    ))
    session.commit()
