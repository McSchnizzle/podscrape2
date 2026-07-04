"""
Standalone regression test for EpisodeRepository.count_scored_since (kanban #2423).

The nightly orchestrator runs with --skip-audio, so the scoring/audio phase
never runs in-band and the in-run "Episodes Scored" count is always 0. That bare
0 was repeatedly misread as a pipeline regression. count_scored_since lets the
orchestrator report the TRUE number of episodes scored out-of-band (by the
dedicated audio cron) in a trailing window.

This test is intentionally self-contained: it builds an in-memory SQLite engine
and creates ONLY the `episodes` table, so it runs even though the shared
conftest `create_all` fixture cannot compile the Postgres-only JSONB columns on
other tables under SQLite. On pre-fix code (no count_scored_since method) it
fails with AttributeError.
"""

from __future__ import annotations

import pytest

pytest.importorskip("sqlalchemy", reason="SQLAlchemy required")

from datetime import datetime, timedelta, UTC

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database.models import Episode, EpisodeRepository
from src.database.sqlalchemy_models import Episode as EpisodeModel


class _TinyDBManager:
    """Minimal DatabaseManager stand-in exposing get_session()."""

    def __init__(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        # Create ONLY the episodes table (avoids JSONB tables SQLite can't build).
        EpisodeModel.__table__.create(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def get_session(self):
        return self.SessionLocal()


@pytest.fixture()
def repo():
    return EpisodeRepository(_TinyDBManager())


def _make(repo, guid, scored_at):
    repo.create(Episode(
        episode_guid=guid,
        feed_id=1,
        title=f"Episode {guid}",
        published_date=datetime.now(UTC),
        audio_url=f"https://example.com/{guid}.mp3",
        status="scored" if scored_at else "pending",
        scores={"AI and Technology": 0.9} if scored_at else None,
        scored_at=scored_at,
    ))


def test_count_scored_since_windows(repo):
    now = datetime.now(UTC)
    _make(repo, "recent-1", now - timedelta(hours=1))
    _make(repo, "recent-2", now - timedelta(hours=23))
    _make(repo, "stale", now - timedelta(days=3))
    _make(repo, "never", None)

    # Trailing-24h window: only the two recent ones.
    assert repo.count_scored_since(now - timedelta(hours=24)) == 2
    # Wider window: catches the stale one too.
    assert repo.count_scored_since(now - timedelta(days=4)) == 3
    # Future cutoff: nothing.
    assert repo.count_scored_since(now + timedelta(hours=1)) == 0


def test_count_scored_since_empty_db(repo):
    assert repo.count_scored_since(datetime.now(UTC) - timedelta(days=1)) == 0
