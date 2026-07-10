"""Tests for scripts/seed_watch_themes.py (watch-themes daily emphasis, Paul 2026-07-10).

Runs the seeder against the in-memory SQLite test DB (conftest.py's
test_db_manager fixture) by monkeypatching get_database_manager so the
script writes nowhere near a real store/ or Supabase instance, per
tests/README.md conventions.
"""
from __future__ import annotations

import pytest

pytest.importorskip("sqlalchemy", reason="SQLAlchemy is required for database integration tests")

import scripts.seed_watch_themes as seed_mod
from src.database.sqlalchemy_models import WatchTheme


@pytest.fixture
def patched_seed_db(monkeypatch, test_db_manager):
    monkeypatch.setattr(seed_mod, "get_database_manager", lambda: test_db_manager)
    return test_db_manager


class TestSeedWatchThemes:
    def test_seed_inserts_five_themes(self, patched_seed_db):
        rc = seed_mod.seed(dry_run=False)
        assert rc == 0

        with patched_seed_db.get_session() as session:
            rows = session.query(WatchTheme).all()
            assert len(rows) == 5
            names = {r.name for r in rows}
            assert names == {name for name, _, _, _ in seed_mod.THEMES}

    def test_seed_sets_scope_per_theme(self, patched_seed_db):
        seed_mod.seed(dry_run=False)
        with patched_seed_db.get_session() as session:
            by_name = {r.name: r for r in session.query(WatchTheme).all()}

        governance = by_name["AI standards, governance, and industry consortiums"]
        assert governance.scope == "both"

        weekly_only = by_name["Claude Code as defacto agentic coding product"]
        assert weekly_only.scope == "weekly"

    def test_seed_is_idempotent(self, patched_seed_db):
        seed_mod.seed(dry_run=False)
        seed_mod.seed(dry_run=False)  # re-run: should skip, not duplicate

        with patched_seed_db.get_session() as session:
            rows = session.query(WatchTheme).all()
            assert len(rows) == 5

    def test_seed_skips_case_insensitive_existing_name(self, patched_seed_db):
        with patched_seed_db.get_session() as session:
            session.add(WatchTheme(
                name="claude code as defacto agentic coding product",
                description="pre-existing row with different casing",
                scope="weekly",
            ))
            session.commit()

        seed_mod.seed(dry_run=False)

        with patched_seed_db.get_session() as session:
            rows = session.query(WatchTheme).all()
            # 1 pre-existing + 4 newly inserted (the 5th name matched case-insensitively)
            assert len(rows) == 5

    def test_dry_run_writes_nothing(self, patched_seed_db):
        rc = seed_mod.seed(dry_run=True)
        assert rc == 0
        with patched_seed_db.get_session() as session:
            assert session.query(WatchTheme).count() == 0

    def test_theme_descriptions_are_nonempty_matcher_prompts(self):
        for name, description, scope, sort_order in seed_mod.THEMES:
            assert len(description) > 40, f"{name} description too short to be a matcher prompt"
            assert scope in ("weekly", "daily", "both")
            assert isinstance(sort_order, int)
