"""Shared helpers for Alembic migrations to handle RLS conditionally.

On Supabase, the ``service_role`` and ``authenticated`` roles exist and RLS
policies are meaningful.  On a local PostgreSQL instance those roles do not
exist, so ``CREATE POLICY … TO service_role`` would raise an error.

These helpers wrap RLS DDL in ``DO $$ … END $$`` blocks that check
``pg_roles`` before executing, making migrations portable across both
environments.
"""

from __future__ import annotations

from alembic import op


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
    """Create a full-access policy for ``service_role`` if the role exists."""
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
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
    """Create a read-only policy for ``authenticated`` if the role exists."""
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
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
    """Create a full-access policy for ``authenticated`` if the role exists."""
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
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
