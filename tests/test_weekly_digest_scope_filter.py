"""Regression test for the weekly-digest scope leak (Codex REQUEST_CHANGES,
Paul 2026-07-10 followup): scripts/run_watch_digest.py must only load
watch_themes with scope in ('weekly', 'both'). A scope='daily' theme is
nightly-emphasis-only and must never appear in the Sunday email or the
Harold POST.
"""
from __future__ import annotations

import pytest

pytest.importorskip("sqlalchemy", reason="SQLAlchemy is required for database integration tests")

from src.database.sqlalchemy_models import WatchTheme
from scripts.run_watch_digest import load_active_weekly_themes


def _add_theme(session, *, name, scope, active=True, sort_order=100):
    session.add(WatchTheme(name=name, description="d", scope=scope,
                           active=active, sort_order=sort_order))


class TestLoadActiveWeeklyThemes:
    """Uses test_db_manager (not test_db_session) -- it drops/recreates all
    tables per test for isolation; test_db_session shares one session-scoped
    engine across the whole file with no reset, which caused cross-test
    data leakage here."""

    def test_weekly_scope_included(self, test_db_manager):
        with test_db_manager.get_session() as session:
            _add_theme(session, name="Weekly theme", scope="weekly")
            session.commit()
            themes = load_active_weekly_themes(session)
        assert {t["name"] for t in themes} == {"Weekly theme"}

    def test_both_scope_included(self, test_db_manager):
        with test_db_manager.get_session() as session:
            _add_theme(session, name="Both theme", scope="both")
            session.commit()
            themes = load_active_weekly_themes(session)
        assert {t["name"] for t in themes} == {"Both theme"}

    def test_daily_scope_excluded(self, test_db_manager):
        """The core regression: a daily-only theme must not leak into the
        Sunday digest."""
        with test_db_manager.get_session() as session:
            _add_theme(session, name="Daily-only theme", scope="daily")
            session.commit()
            themes = load_active_weekly_themes(session)
        assert themes == []

    def test_mixed_scopes_filters_correctly(self, test_db_manager):
        with test_db_manager.get_session() as session:
            _add_theme(session, name="Weekly theme", scope="weekly", sort_order=10)
            _add_theme(session, name="Both theme", scope="both", sort_order=20)
            _add_theme(session, name="Daily-only theme", scope="daily", sort_order=30)
            session.commit()
            themes = load_active_weekly_themes(session)
        names = {t["name"] for t in themes}
        assert names == {"Weekly theme", "Both theme"}
        assert "Daily-only theme" not in names

    def test_inactive_theme_excluded_regardless_of_scope(self, test_db_manager):
        with test_db_manager.get_session() as session:
            _add_theme(session, name="Inactive weekly", scope="weekly", active=False)
            session.commit()
            themes = load_active_weekly_themes(session)
        assert themes == []

    def test_theme_ids_filter_still_respects_scope(self, test_db_manager):
        """--theme-ids is a manual testing override, but must not be able to
        pull a daily-only theme into the weekly run."""
        with test_db_manager.get_session() as session:
            _add_theme(session, name="Daily-only theme", scope="daily")
            session.commit()
            daily_theme_id = session.query(WatchTheme).one().id
            themes = load_active_weekly_themes(session, theme_ids=[daily_theme_id])
        assert themes == []
