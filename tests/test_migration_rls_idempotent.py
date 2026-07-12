"""CI-safe regression tests for the RLS migration helpers' idempotency guard
(kanban #2711 AC1).

``src/migration_rls.py`` builds the RLS ``CREATE POLICY`` DDL that Alembic
migrations emit. Postgres has no ``CREATE POLICY IF NOT EXISTS``, and the
migration history creates the SAME policy on the SAME table from two different
revisions (``topics`` in 1397ff315ac6 + 627ebea71c37; ``episode_topics`` in
d8f9e2a7b5c4 + a3c2199ce1a8). Without a ``pg_policies`` existence guard the
second ``CREATE POLICY`` aborts ``alembic upgrade head`` with
``DuplicateObject`` ("policy ... already exists") on any DB where the
``service_role`` / ``authenticated`` roles exist.

These tests pin that every ``create_*_policy`` helper emits BOTH the
``pg_roles`` guard AND the ``pg_policies(schemaname, tablename, policyname)``
guard, without needing a live Postgres (they capture the generated SQL). The
end-to-end proof -- ``alembic upgrade head`` running clean twice in a row
against a fresh local database whose roles exist -- is recorded on the #2711
branch; this file guards against a silent regression back to the
pg_roles-only guard in CI where no Postgres is available.
"""

import pytest

import src.migration_rls as migration_rls


@pytest.fixture
def captured_sql(monkeypatch):
    """Capture the SQL each helper hands to ``op.execute`` instead of running
    it against a database."""
    calls = []
    monkeypatch.setattr(migration_rls.op, "execute", lambda sql: calls.append(str(sql)))
    return calls


def _assert_idempotent_guard(sql, *, schema, table, policy, role):
    # Original portability guard (role must exist) is preserved.
    assert "pg_roles" in sql
    assert f"rolname = '{role}'" in sql
    # #2711 idempotency guard: skip when the policy already exists.
    assert "pg_policies" in sql
    assert "NOT EXISTS" in sql
    assert f"schemaname = '{schema}'" in sql
    assert f"tablename = '{table}'" in sql
    assert f"policyname = '{policy}'" in sql
    # The actual policy is still created (targets the fully-qualified name).
    assert f'CREATE POLICY "{policy}"' in sql


def test_service_role_policy_has_pg_policies_guard(captured_sql):
    migration_rls.create_service_role_policy("topics")
    (sql,) = captured_sql
    _assert_idempotent_guard(
        sql, schema="public", table="topics",
        policy="service_role_policy", role="service_role",
    )


def test_authenticated_read_policy_has_pg_policies_guard(captured_sql):
    migration_rls.create_authenticated_read_policy("episode_topics")
    (sql,) = captured_sql
    _assert_idempotent_guard(
        sql, schema="public", table="episode_topics",
        policy="authenticated_read_policy", role="authenticated",
    )


def test_authenticated_all_policy_has_pg_policies_guard(captured_sql):
    migration_rls.create_authenticated_all_policy("web_settings")
    (sql,) = captured_sql
    _assert_idempotent_guard(
        sql, schema="public", table="web_settings",
        policy="authenticated_users_policy", role="authenticated",
    )


def test_custom_policy_name_flows_into_pg_policies_check(captured_sql):
    migration_rls.create_service_role_policy("topics", policy_name="custom_sr_policy")
    (sql,) = captured_sql
    assert "policyname = 'custom_sr_policy'" in sql
    assert 'CREATE POLICY "custom_sr_policy"' in sql


def test_schema_qualified_table_name_is_split_for_pg_policies_check(captured_sql):
    migration_rls.create_service_role_policy("analytics.topics")
    (sql,) = captured_sql
    # pg_policies exposes schema/table as separate unquoted columns.
    assert "schemaname = 'analytics'" in sql
    assert "tablename = 'topics'" in sql
    # CREATE POLICY still targets the fully-qualified name.
    assert "ON analytics.topics" in sql


def test_split_schema_table_defaults_to_public():
    assert migration_rls._split_schema_table("topics") == ("public", "topics")
    assert migration_rls._split_schema_table("public.topics") == ("public", "topics")
