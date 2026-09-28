"""Discovery must not lose YouTube feeds to YouTube's intermittent 404/500 bursts.

2026-09-27: the nightly digest carried 1 episode. Since 2026-08-31, 20-26 of the 41 feeds (nearly
all YouTube) failed nightly with 404/500 at 21:00, while the same URLs answered 200 the next
morning. The single 5s retry gave up for the night. Failed YouTube feeds are now retried in
deferred passes (DEFERRED_PASS_DELAYS_S).
"""
import importlib.util
import logging
import sys
import types
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def rd(monkeypatch):
    spec = importlib.util.spec_from_file_location("run_discovery_under_test", ROOT / "scripts" / "run_discovery.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["run_discovery_under_test"] = mod
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "DEFERRED_PASS_DELAYS_S", (0, 0))
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    return mod


FEED_XML = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"
 xmlns:yt="http://www.youtube.com/xml/schemas/2015"><title>c</title>
 <entry><id>yt:video:abc{n}</id><title>Long video {n}</title>
 <link rel="alternate" href="https://www.youtube.com/watch?v=abc{n}"/>
 <published>{d}T10:00:00+00:00</published></entry></feed>"""


def _runner(rd, feeds):
    r = object.__new__(rd.DiscoveryRunner)
    r.logger = logging.getLogger("t")
    r.dry_run = True
    r.episode_guid = None
    r.limit = 10
    r.days_back = 5
    r.rss_feeds = feeds
    r.episode_repo = mock.Mock(get_by_episode_guid=mock.Mock(return_value=None))
    r.feed_repo = mock.Mock()
    return r


def _resp(code, body=b""):
    return types.SimpleNamespace(
        status_code=code, content=body,
        raise_for_status=(lambda: None) if code == 200 else
        (lambda: (_ for _ in ()).throw(Exception(f"{code} Client Error"))))


def test_youtube_feed_failing_first_pass_is_recovered_in_a_deferred_pass(rd, monkeypatch):
    from datetime import date
    today = date.today().isoformat()
    feeds = [{"id": 1, "url": "https://www.youtube.com/feeds/videos.xml?channel_id=A", "name": "A", "feed_type": "youtube"},
             {"id": 2, "url": "https://www.youtube.com/feeds/videos.xml?channel_id=B", "name": "B", "feed_type": "youtube"}]
    calls = {"A": 0, "B": 0}

    def fake_get(url, timeout=0, headers=None):
        key = url[-1]
        calls[key] += 1
        # A works; B fails both first-pass attempts (initial + inline retry), then recovers.
        if key == "B" and calls["B"] <= 2:
            return _resp(404)
        return _resp(200, FEED_XML.replace(b"{n}", key.encode()).replace(b"{d}", today.encode()))

    monkeypatch.setattr(rd.requests, "get", fake_get)
    out = _runner(rd, feeds).discover_episodes()
    titles = sorted(e["title"] for e in out["episodes"])
    assert titles == ["Long video A", "Long video B"]
    assert calls["B"] == 3


def test_feed_that_never_recovers_is_reported_and_bounded(rd, monkeypatch, caplog):
    feeds = [{"id": 3, "url": "https://www.youtube.com/feeds/videos.xml?channel_id=C", "name": "Dead", "feed_type": "youtube"}]
    n = {"c": 0}

    def always_404(url, timeout=0, headers=None):
        n["c"] += 1
        return _resp(404)

    monkeypatch.setattr(rd.requests, "get", always_404)
    with caplog.at_level(logging.WARNING):
        out = _runner(rd, feeds).discover_episodes()
    assert out["episodes"] == []
    assert n["c"] == 2 * (len(rd.DEFERRED_PASS_DELAYS_S) + 1)  # initial+inline retry, per pass
    assert "Feeds unreachable after all passes (1): Dead" in caplog.text


def test_non_youtube_failure_is_not_retried_in_passes(rd, monkeypatch):
    feeds = [{"id": 4, "url": "https://example.com/rss", "name": "Pod", "feed_type": "rss"}]
    n = {"c": 0}

    def fail(url, timeout=0, headers=None):
        n["c"] += 1
        return _resp(500)

    monkeypatch.setattr(rd.requests, "get", fail)
    _runner(rd, feeds).discover_episodes()
    assert n["c"] == 1
