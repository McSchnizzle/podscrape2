"""Bakeoff episodes never enter the nightly pipeline's selections.

They are voiced and published only by explicit digest id. These tests run
the three real nightly selectors (TTS pending, nightly publishing, Phase 8
briefing) against an in-memory SQLite database or a fake repository.
"""
from __future__ import annotations

import importlib.util
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy.orm import sessionmaker

from src.database.models import DigestRepository
from src.database.sqlalchemy_models import Digest as DigestModel
from src.publishing.bakeoff import BAKEOFF_TOPIC
from src.publishing.creator_briefing import select_digest

TODAY = date(2026, 10, 3)


def _row(topic, minute, **kw):
    base = dict(topic=topic, digest_date=TODAY,
                digest_timestamp=datetime(2026, 10, 3, 12, minute),
                script_content="SPEAKER_1: hi", episode_count=3)
    base.update(kw)
    return DigestModel(**base)


def test_tts_pending_selection_excludes_bakeoff(test_db_manager):
    s = test_db_manager.SessionLocal()
    s.add_all([_row("AI and Technology", 1), _row(BAKEOFF_TOPIC, 2)])
    s.commit(); s.close()
    pending = DigestRepository(test_db_manager).get_digests_pending_tts()
    assert [d.topic for d in pending] == ["AI and Technology"]


def test_briefing_never_selects_a_bakeoff_episode(test_database_engine):
    from src.database.sqlalchemy_models import Base
    Base.metadata.drop_all(test_database_engine)
    Base.metadata.create_all(test_database_engine)
    s = sessionmaker(bind=test_database_engine)()
    published = dict(status="published", github_url="https://example.invalid/r")
    s.add_all([_row("AI and Technology", 1, digest_date=TODAY - timedelta(days=1), **published),
               _row(BAKEOFF_TOPIC, 2, **published)])
    s.commit()
    chosen = select_digest(s, TODAY)
    assert chosen is not None and chosen.topic == "AI and Technology"
    s.close()


def test_nightly_publishing_skips_bakeoff_rows(monkeypatch):
    path = Path(__file__).parent.parent / "scripts" / "run_publishing.py"
    spec = importlib.util.spec_from_file_location("run_publishing_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    runner = object.__new__(mod.PublishingPipelineRunner)
    runner.logger = logging.getLogger("t")
    rows = [SimpleNamespace(id=i, topic=t, digest_date=TODAY, mp3_path="x.mp3", mp3_title="t",
                            mp3_summary="s", mp3_duration_seconds=300,
                            github_url="https://example.invalid/r", generated_at=None)
            for i, t in ((1, "AI and Technology"), (2, BAKEOFF_TOPIC))]
    runner.digest_repo = SimpleNamespace(get_recent_digests=lambda days: rows)
    found = runner.find_unpublished_digests(days_back=30)
    assert [d["id"] for d in found] == [1]
