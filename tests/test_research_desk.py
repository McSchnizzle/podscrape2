"""
Tests for scripts/research_desk.py — the weekly web-research injector
(Paul 2026-07-10, kanban: research desk injector).

No network calls: the OpenAI client and article fetch are mocked/monkeypatched.
Uses the standard in-memory SQLite test_db_manager fixture (tests/conftest.py),
never touching the real store/ or podcast Postgres database.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("sqlalchemy", reason="SQLAlchemy is required for database integration tests")

from scripts import research_desk as rd
from src.database.models import Episode


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

def make_response(output_text: str):
    return SimpleNamespace(output_text=output_text)


class FakeResponses:
    def __init__(self, queue):
        self._queue = list(queue)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._queue:
            raise AssertionError("FakeResponses.create called more times than expected")
        return self._queue.pop(0)


class FakeClient:
    def __init__(self, queue):
        self.responses = FakeResponses(queue)


def search_payload(candidates):
    return make_response(json.dumps({"candidates": candidates}))


def triage_payload(score, rationale="Genuinely interesting cross-industry news."):
    return make_response(json.dumps({"score": score, "rationale": rationale}))


GOOD_CANDIDATE = {
    "title": "New Interop Spec Ratified",
    "url": "https://example-news.test/interop-spec",
    "publication": "Standards Weekly",
    "author": "Jane Reporter",
    "published_date": "2026-07-08",
    "summary": "A short summary of the new spec.",
}

LONG_ARTICLE_BODY = "This is a paragraph about the new interoperability spec. " * 30
assert len(LONG_ARTICLE_BODY) >= rd.MIN_TRANSCRIPT_CHARS


# ---------------------------------------------------------------------------
# Pure-function unit tests
# ---------------------------------------------------------------------------

def test_get_reasoning_effort():
    assert rd.get_reasoning_effort("gpt-5.2") == "medium"
    assert rd.get_reasoning_effort("gpt-5.2-pro") == "medium"
    assert rd.get_reasoning_effort("gpt-5-mini") == "minimal"


def test_build_episode_guid_deterministic():
    guid1 = rd.build_episode_guid("https://example.com/a")
    guid2 = rd.build_episode_guid("https://example.com/a")
    guid3 = rd.build_episode_guid("https://example.com/b")
    assert guid1 == guid2
    assert guid1 != guid3
    assert guid1.startswith("harold-web-research-")
    assert len(guid1) == len("harold-web-research-") + 16


def test_parse_candidates_handles_code_fence():
    payload = "```json\n" + json.dumps({"candidates": [GOOD_CANDIDATE]}) + "\n```"
    response = make_response(payload)
    candidates = rd.parse_candidates(response, "test-angle")
    assert len(candidates) == 1
    assert candidates[0].title == GOOD_CANDIDATE["title"]
    assert candidates[0].url == GOOD_CANDIDATE["url"]
    assert candidates[0].query_angle == "test-angle"


def test_parse_candidates_skips_items_missing_url_or_title():
    payload = json.dumps({"candidates": [
        {**GOOD_CANDIDATE, "url": ""},
        {**GOOD_CANDIDATE, "title": ""},
        GOOD_CANDIDATE,
    ]})
    candidates = rd.parse_candidates(make_response(payload), "test-angle")
    assert len(candidates) == 1


def test_build_transcript_header_with_and_without_author():
    candidate = rd.Candidate(
        title="T", url="https://x.test/y", publication="Pub", author="Al Author",
        published_date="2026-07-01", summary="s", query_angle="a",
    )
    transcript = rd.build_transcript(candidate, "BODY TEXT")
    header, blank, body = transcript.split("\n", 2)
    assert header == "Written article from Pub, by Al Author, published 2026-07-01. https://x.test/y"
    assert blank == ""
    assert body == "BODY TEXT"

    candidate_no_author = rd.Candidate(**{**candidate.__dict__, "author": None})
    transcript2 = rd.build_transcript(candidate_no_author, "BODY TEXT")
    header2 = transcript2.split("\n", 1)[0]
    assert header2 == "Written article from Pub, published 2026-07-01. https://x.test/y"


# ---------------------------------------------------------------------------
# Integration tests (in-memory SQLite via test_db_manager)
# ---------------------------------------------------------------------------

def test_inject_produces_correct_row_shape(test_db_manager, monkeypatch, tmp_path):
    monkeypatch.setattr(rd, "fetch_article_text", lambda url, timeout=15.0: LONG_ARTICLE_BODY)

    client = FakeClient([
        search_payload([GOOD_CANDIDATE]),
        triage_payload(0.9),
    ])
    ledger_path = tmp_path / "ledger.json"

    stats = rd.run(
        db_manager=test_db_manager, client=client, model="gpt-5.2",
        max_inject=2, dry_run=False, ledger_path=ledger_path,
        angles=[("test-angle", "test query")],
    )

    assert stats.injected == 1
    assert not stats.fatal

    from src.database.models import get_episode_repo
    episode_repo = get_episode_repo(test_db_manager)
    expected_guid = rd.build_episode_guid(GOOD_CANDIDATE["url"])
    episode = episode_repo.get_by_episode_guid(expected_guid)

    assert episode is not None
    assert episode.title == "New Interop Spec Ratified — Standards Weekly"
    assert episode.audio_url == GOOD_CANDIDATE["url"]
    assert episode.scores == {"AI and Technology": 0.9}
    assert episode.status == "scored"
    assert episode.scored_at is not None
    assert episode.transcript_generated_at is not None
    assert episode.transcript_word_count == len(episode.transcript_content.split())
    assert episode.transcript_content.startswith(
        "Written article from Standards Weekly, by Jane Reporter, published 2026-07-08. "
        f"{GOOD_CANDIDATE['url']}\n\n"
    )
    assert len(episode.transcript_content) >= rd.MIN_TRANSCRIPT_CHARS
    # published_date must be "now", never backdated to the article's original date
    assert abs(episode.published_date - datetime.now()) < timedelta(minutes=2)

    # ledger got the entry
    ledger = json.loads(ledger_path.read_text())
    assert len(ledger) == 1
    assert ledger[0]["url"] == GOOD_CANDIDATE["url"]
    assert ledger[0]["guid"] == expected_guid


def test_ledger_dedupe_prevents_reinjection(test_db_manager, monkeypatch, tmp_path):
    monkeypatch.setattr(rd, "fetch_article_text", lambda url, timeout=15.0: LONG_ARTICLE_BODY)
    ledger_path = tmp_path / "ledger.json"

    client1 = FakeClient([search_payload([GOOD_CANDIDATE]), triage_payload(0.9)])
    stats1 = rd.run(
        db_manager=test_db_manager, client=client1, model="gpt-5.2",
        max_inject=2, dry_run=False, ledger_path=ledger_path,
        angles=[("test-angle", "test query")],
    )
    assert stats1.injected == 1

    # Second run: same candidate resurfaces from search, but the ledger
    # should short-circuit it before a triage call is even made.
    client2 = FakeClient([search_payload([GOOD_CANDIDATE])])
    stats2 = rd.run(
        db_manager=test_db_manager, client=client2, model="gpt-5.2",
        max_inject=2, dry_run=False, ledger_path=ledger_path,
        angles=[("test-angle", "test query")],
    )
    assert stats2.injected == 0
    assert stats2.triaged == 0
    assert any("already in ledger" in reason for _, reason in stats2.skipped)

    ledger = json.loads(ledger_path.read_text())
    assert len(ledger) == 1  # append-only, no duplicate entry


def test_short_article_and_short_summary_is_skipped(test_db_manager, monkeypatch, tmp_path):
    # Fetch fails entirely, and the search summary is short, so the padded
    # fallback also stays under MIN_TRANSCRIPT_CHARS.
    monkeypatch.setattr(rd, "fetch_article_text", lambda url, timeout=15.0: None)
    short_candidate = {**GOOD_CANDIDATE, "summary": "Too short."}

    client = FakeClient([search_payload([short_candidate]), triage_payload(0.9)])
    ledger_path = tmp_path / "ledger.json"

    stats = rd.run(
        db_manager=test_db_manager, client=client, model="gpt-5.2",
        max_inject=2, dry_run=False, ledger_path=ledger_path,
        angles=[("test-angle", "test query")],
    )

    assert stats.injected == 0
    assert any("under 1000 chars" in reason for _, reason in stats.skipped)

    from src.database.models import get_episode_repo
    episode_repo = get_episode_repo(test_db_manager)
    assert episode_repo.get_by_episode_guid(rd.build_episode_guid(GOOD_CANDIDATE["url"])) is None
    assert not ledger_path.exists()


def test_dry_run_inserts_nothing(test_db_manager, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(rd, "fetch_article_text", lambda url, timeout=15.0: LONG_ARTICLE_BODY)
    client = FakeClient([search_payload([GOOD_CANDIDATE]), triage_payload(0.9)])
    ledger_path = tmp_path / "ledger.json"

    stats = rd.run(
        db_manager=test_db_manager, client=client, model="gpt-5.2",
        max_inject=2, dry_run=True, ledger_path=ledger_path,
        angles=[("test-angle", "test query")],
    )

    assert stats.qualified == 1
    assert not ledger_path.exists()

    from src.database.models import get_episode_repo
    episode_repo = get_episode_repo(test_db_manager)
    assert episode_repo.get_by_episode_guid(rd.build_episode_guid(GOOD_CANDIDATE["url"])) is None

    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "New Interop Spec Ratified" in out


def test_pseudo_feed_is_idempotent(test_db_manager):
    from src.database.models import get_feed_repo
    feed_repo = get_feed_repo(test_db_manager)

    feed_id_1 = rd.ensure_pseudo_feed(feed_repo)
    feed_id_2 = rd.ensure_pseudo_feed(feed_repo)

    assert feed_id_1 == feed_id_2
    feed = feed_repo.get_by_url(rd.PSEUDO_FEED_URL)
    assert feed is not None
    assert feed.active is False
    assert feed.title == rd.PSEUDO_FEED_TITLE


def test_all_search_angles_failing_is_fatal_and_injects_nothing(test_db_manager, tmp_path):
    class ExplodingResponses:
        def create(self, **kwargs):
            raise RuntimeError("simulated API outage")

    class ExplodingClient:
        def __init__(self):
            self.responses = ExplodingResponses()

    stats = rd.run(
        db_manager=test_db_manager, client=ExplodingClient(), model="gpt-5.2",
        max_inject=2, dry_run=False, ledger_path=tmp_path / "ledger.json",
        angles=[("test-angle", "test query")],
    )
    assert stats.fatal is True
    assert stats.injected == 0
