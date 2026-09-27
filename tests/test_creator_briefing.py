"""Phase 8 creator briefing email.

The properties worth guarding:

- No link reaches the reader unless the web search surfaced it AND it answers.
  web_search also writes "([site](url))" citations into prose, which would
  bypass that check entirely, so prose is scrubbed.
- Model output is escaped, and only https hrefs are emitted.
- The repo is public: recipient addresses live in web_settings, never here.
- Phase 8 is actually wired into the orchestrator after dedup.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

from src.publishing import creator_briefing as cb

ROOT = Path(__file__).resolve().parent.parent


def _story(**over):
    story = {
        "kicker": "MODEL WARS",
        "headline": "A model launched",
        "what_happened": "It launched.",
        "why_it_matters": "People care.",
        "video_angle": "Race them.",
        "dig_deeper": ["Is it cheaper?", "Who wins?"],
        "news_search_query": "model launch",
        "confidence": "confirmed",
        "heard_on": [1],
        "sources": [],
    }
    story.update(over)
    return story


def _draft(stories):
    return {
        "subject": "Tonight",
        "opener": "Hi.",
        "stories": stories,
        "rabbit_hole": {"title": "Hole", "blurb": "Deep.", "search_query": "hole"},
        "sign_off": "Bye.",
    }


def _material(**over):
    m = dict(
        digest_id=1, digest_date=date(2026, 9, 25), episode_title="Ep", episode_summary="",
        release_url="https://github.com/example/releases/tag/daily-2026-09-25", script="",
        arcs=[], episodes=[cb.SourceEpisode("Show", "Episode One", "https://www.youtube.com/watch?v=abc")],
    )
    m.update(over)
    return cb.BriefingMaterial(**m)


# ---------------------------------------------------------------------------
# Link verification
# ---------------------------------------------------------------------------

def test_source_not_surfaced_by_search_is_dropped():
    draft = _draft([_story(sources=[{"title": "t", "publication": "p", "url": "https://example.com/made-up"}])])
    report = cb.verify_sources(draft, surfaced=set(), checker=lambda u: (True, "HTTP 200"))
    assert draft["stories"][0]["sources"] == []
    assert report.dropped == [("https://example.com/made-up", "not in search results")]


def test_dead_source_is_dropped_even_if_surfaced():
    url = "https://example.com/gone"
    draft = _draft([_story(sources=[{"title": "t", "publication": "p", "url": url}])])
    report = cb.verify_sources(draft, surfaced={url}, checker=lambda u: (False, "HTTP 404"))
    assert draft["stories"][0]["sources"] == []
    assert report.dropped == [(url, "HTTP 404")]


def test_surfaced_live_source_is_kept_with_tracking_stripped():
    raw = "https://example.com/story?utm_source=openai"
    draft = _draft([_story(sources=[{"title": "t", "publication": "p", "url": raw}])])
    checked = []
    report = cb.verify_sources(draft, surfaced={"https://example.com/story"},
                               checker=lambda u: (checked.append(u), (True, "HTTP 200"))[1])
    assert draft["stories"][0]["sources"][0]["url"] == "https://example.com/story"
    assert checked == ["https://example.com/story"]
    assert report.kept == 1


def test_duplicate_sources_collapse_and_cap_at_three():
    urls = [f"https://example.com/{i}" for i in range(5)]
    sources = [{"title": "t", "publication": "p", "url": u} for u in urls + urls[:1]]
    draft = _draft([_story(sources=sources)])
    cb.verify_sources(draft, surfaced=set(urls), checker=lambda u: (True, "HTTP 200"))
    assert [s["url"] for s in draft["stories"][0]["sources"]] == urls[:3]


# ---------------------------------------------------------------------------
# Prose cleaning
# ---------------------------------------------------------------------------

def test_inline_citations_and_urls_are_stripped_from_prose():
    text = ("Opus 5.5 launched. ([anthropic.com](https://www.anthropic.com/x?trk=a)) "
            "See [the list](https://github.com/y) and https://t.co/abc.")
    cleaned = cb.clean_prose(text)
    assert "http" not in cleaned
    assert cleaned == "Opus 5.5 launched. See the list and."


def test_em_dashes_and_trailing_signature_are_removed():
    draft = cb.clean_draft({**_draft([_story(what_happened="Big — news")]),
                            "sign_off": "Go make something. — Harold"})
    assert draft["stories"][0]["what_happened"] == "Big, news"
    assert draft["sign_off"] == "Go make something."


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def test_model_text_is_escaped_and_only_https_hrefs_render():
    story = _story(headline="<script>alert(1)</script>",
                   sources=[{"title": "ok", "publication": "p", "url": "https://example.com/a"},
                            {"title": "bad", "publication": "p", "url": "javascript:alert(1)"}])
    out = cb.render_html(_draft([story]), _material(), reader="Sam")
    assert "<script>alert(1)" not in out
    assert "&lt;script&gt;" in out
    assert "javascript:" not in out
    assert 'href="https://example.com/a"' in out


def test_every_story_gets_search_links_and_valid_heard_on_only():
    story = _story(heard_on=[1, 7, 0])
    out = cb.render_html(_draft([story]), _material(), reader="Sam")
    assert "https://news.google.com/search?q=model+launch" in out
    assert "https://www.youtube.com/results?search_query=model+launch" in out
    assert out.count("Episode One") == 1
    assert "Sam&#x27;s AI Desk" in out


def test_preview_banner_only_on_preview():
    assert "Preview edition" in cb.render_html(_draft([_story()]), _material(), preview=True)
    assert "Preview edition" not in cb.render_html(_draft([_story()]), _material())
    assert cb.render_text(_draft([_story()]), _material(), preview=True).startswith("PREVIEW EDITION")


def test_html_uses_tokens_not_raw_colors():
    """Colors come from TOKENS (mirrors ~/.claude/design/tokens.css)."""
    source = (ROOT / "src/publishing/creator_briefing.py").read_text()
    body = source.split("TOKENS = {", 1)[1].split("\n}\n", 1)[1]
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b", body)


# ---------------------------------------------------------------------------
# Config and wiring
# ---------------------------------------------------------------------------

def test_recipients_parse_and_reject_garbage():
    assert cb.parse_recipients("a@example.com, b@example.com;") == ["a@example.com", "b@example.com"]
    assert cb.parse_recipients("") == []
    with pytest.raises(cb.BriefingError):
        cb.parse_recipients("not an address")


def test_no_recipient_addresses_in_public_source():
    from src.config.web_config import DEFAULTS
    assert DEFAULTS[("creator_briefing", "recipients")]["default"] == ""
    assert DEFAULTS[("creator_briefing", "enabled")]["default"] is False
    for rel in ("src/publishing/creator_briefing.py", "scripts/run_briefing_email.py", "src/config/web_config.py"):
        addrs = set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", (ROOT / rel).read_text()))
        assert addrs <= {cb.SENDER_ADDRESS, "someone@example.com"}, (rel, addrs)


def test_phase_8_is_wired_after_dedup():
    src = (ROOT / "run_full_pipeline_orchestrator.py").read_text()
    dedup = src.index("self.run_phase_script('scripts/run_dedup.py')")
    briefing = src.index("self.run_phase_script('scripts/run_briefing_email.py')")
    summary = src.index("# Final summary")
    assert dedup < briefing < summary
