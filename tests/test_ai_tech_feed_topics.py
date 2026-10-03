"""The AI & Technology feed (the Spotify show) carries the bakeoff episodes.

The web app has no TypeScript test runner, so this pins the route's contract
from Python: its topic list includes BAKEOFF_TOPIC (one source of truth with
the nightly exclusions) and the AI topic, and the query binds that list.
Regression for 2026-10-03: five bakeoff episodes reached /daily-digest.xml but
not /ai-tech-digest.xml, which is the feed the show actually uses.
"""
import re
from pathlib import Path

from src.publishing.bakeoff import BAKEOFF_TOPIC

ROUTE = (Path(__file__).parent.parent / "web_ui_hosted" / "app" / "api" / "rss"
         / "ai-tech-digest" / "route.ts").read_text()


def _feed_topics():
    m = re.search(r"const FEED_TOPICS = \[([^\]]*)\];", ROUTE)
    assert m, "FEED_TOPICS constant missing"
    consts = dict(re.findall(r"const (\w+) = '([^']*)';", ROUTE))
    out = []
    for item in (x.strip() for x in m.group(1).split(",")):
        out.append(item.strip("'") if item.startswith("'") else consts[item])
    return out


def test_feed_carries_ai_topic_and_bakeoff():
    assert _feed_topics() == ["AI and Technology", BAKEOFF_TOPIC]


def test_query_binds_the_topic_list():
    assert "WHERE topic = ANY($1::text[])" in ROUTE
    assert "[FEED_TOPICS]" in ROUTE
    assert "WHERE topic = $1\n" not in ROUTE


def test_feed_still_requires_published_audio():
    for clause in ("github_url IS NOT NULL", "mp3_path IS NOT NULL", "LIMIT 50"):
        assert clause in ROUTE
