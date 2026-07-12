"""Shared helpers for Alembic migrations to handle RLS conditionally.

On Supabase, the ``service_role`` and ``authenticated`` roles exist and RLS
policies are meaningful.  On a local PostgreSQL instance those roles do not
exist, so ``CREATE POLICY … TO service_role`` would raise an error.

These helpers wrap RLS DDL in ``DO $$ … END $$`` blocks that check
``pg_roles`` before executing, making migrations portable across both
environments.

Idempotency (kanban #2711): the ``create_*_policy`` helpers ALSO check
``pg_policies`` for an existing (schemaname, tablename, policyname) row before
``CREATE POLICY``.  Postgres has no ``CREATE POLICY IF NOT EXISTS``, and the
migration history creates the SAME policy on the SAME table from two different
revisions (``topics`` in 1397ff315ac6 and 627ebea71c37; ``episode_topics`` in
d8f9e2a7b5c4 and a3c2199ce1a8).  On any DB where the ``service_role`` /
``authenticated`` roles exist, the second ``CREATE POLICY`` would raise
``DuplicateObject`` (``policy "…" for table "…" already exists``) and abort
``alembic upgrade head``.  The pg_policies guard makes each helper a no-op when
its policy is already present, so the whole chain is safe to run against a DB
whose roles (and therefore policies) already exist.
"""

from __future__ import annotations

from alembic import op


def _split_schema_table(table_name: str) -> tuple[str, str]:
    """Split an optionally schema-qualified table name into (schema, table).

    ``pg_policies`` exposes ``schemaname`` and ``tablename`` as separate
    unquoted columns, so the existence check needs the bare parts. Callers in
    this repo pass unqualified names (e.g. ``"topics"``), which resolve to the
    ``public`` schema; ``"public.topics"`` is also handled.
    """
    if "." in table_name:
        schema, table = table_name.split(".", 1)
    else:
        schema, table = "public", table_name
    return schema.strip('"'), table.strip('"')


def enable_rls(table_name: str) -> None:
    """Enable row-level security on *table_name* (idempotent)."""
    op.execute(
        f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;"
    )


def disable_rls(table_name: str) -> None:
    """Disable row-level security on *table_name*."""
    op.execute(
        f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY;"
    )


def create_service_role_policy(
    table_name: str,
    *,
    policy_name: str = "service_role_policy",
) -> None:
    """Create a full-access policy for ``service_role`` if the role exists and
    the policy is not already present (idempotent -- see module docstring)."""
    schema, table = _split_schema_table(table_name)
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role')
               AND NOT EXISTS (
                   SELECT 1 FROM pg_policies
                   WHERE schemaname = '{schema}'
                     AND tablename = '{table}'
                     AND policyname = '{policy_name}'
               ) THEN
                CREATE POLICY "{policy_name}" ON {table_name}
                FOR ALL TO service_role
                USING (true) WITH CHECK (true);
            END IF;
        END $$;
        """
    )


def create_authenticated_read_policy(
    table_name: str,
    *,
    policy_name: str = "authenticated_read_policy",
) -> None:
    """Create a read-only policy for ``authenticated`` if the role exists and
    the policy is not already present (idempotent -- see module docstring)."""
    schema, table = _split_schema_table(table_name)
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated')
               AND NOT EXISTS (
                   SELECT 1 FROM pg_policies
                   WHERE schemaname = '{schema}'
                     AND tablename = '{table}'
                     AND policyname = '{policy_name}'
               ) THEN
                CREATE POLICY "{policy_name}" ON {table_name}
                FOR SELECT TO authenticated
                USING (true);
            END IF;
        END $$;
        """
    )


def create_authenticated_all_policy(
    table_name: str,
    *,
    policy_name: str = "authenticated_users_policy",
) -> None:
    """Create a full-access policy for ``authenticated`` if the role exists and
    the policy is not already present (idempotent -- see module docstring)."""
    schema, table = _split_schema_table(table_name)
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated')
               AND NOT EXISTS (
                   SELECT 1 FROM pg_policies
                   WHERE schemaname = '{schema}'
                     AND tablename = '{table}'
                     AND policyname = '{policy_name}'
               ) THEN
                CREATE POLICY "{policy_name}" ON {table_name}
                FOR ALL TO authenticated
                USING (true) WITH CHECK (true);
            END IF;
        END $$;
        """
    )


def drop_policy(table_name: str, policy_name: str) -> None:
    """Drop a policy if it exists."""
    op.execute(
        f'DROP POLICY IF EXISTS "{policy_name}" ON {table_name};'
    )
