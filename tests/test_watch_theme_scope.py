"""Tests for watch_themes.scope (watch-themes daily emphasis, Paul 2026-07-10).

Regression guard for the migration + model contract, mirroring the pattern
used in test_database_models.py::test_digest_timestamp_schema_contract_is_migrated
(reads the model columns AND the migration source, rather than literally
running Alembic against SQLite -- production migrations use Postgres-only
DDL like op.create_check_constraint, which the in-memory SQLite test DB in
conftest.py builds via Base.metadata.create_all() instead).
"""
from __future__ import annotations

import pytest

pytest.importorskip("sqlalchemy", reason="SQLAlchemy is required for database integration tests")

from pathlib import Path

from src.database.sqlalchemy_models import WatchTheme


class TestWatchThemeScopeSchemaContract:
    def test_scope_column_exists_with_expected_defaults(self):
        columns = WatchTheme.__table__.c
        assert "scope" in columns
        scope_col = columns["scope"]
        assert not scope_col.nullable
        assert scope_col.default.arg == "weekly"
        assert scope_col.server_default.arg == "weekly"

    def test_scope_index_registered(self):
        index_names = {ix.name for ix in WatchTheme.__table__.indexes}
        assert "ix_watch_themes_scope" in index_names

    def test_migration_adds_scope_idempotently(self):
        project_root = Path(__file__).resolve().parents[1]
        migration_path = project_root / (
            "alembic/versions/m9i0j1k2l3m4_add_watch_theme_scope.py"
        )
        migration = migration_path.read_text()

        assert "down_revision = 'l8h9i0j1k2l3'" in migration
        assert "op.add_column" in migration
        assert "'scope'" in migration
        assert "server_default='weekly'" in migration
        # Idempotent guard pattern used across this repo's migrations
        assert "insp.get_columns" in migration
        assert "if 'scope' not in cols" in migration
        assert "ck_watch_themes_scope" in migration
        assert "scope IN ('weekly', 'daily', 'both')" in migration


class TestWatchThemeModelDefaults(object):
    def test_new_instance_defaults_to_weekly_scope(self, test_db_manager):
        with test_db_manager.get_session() as session:
            theme = WatchTheme(name="Test theme", description="A description")
            session.add(theme)
            session.commit()
            session.refresh(theme)
            assert theme.scope == "weekly"

    def test_explicit_scope_persists(self, test_db_manager):
        with test_db_manager.get_session() as session:
            theme = WatchTheme(
                name="Daily theme", description="A description", scope="both",
            )
            session.add(theme)
            session.commit()
            session.refresh(theme)
            assert theme.scope == "both"
