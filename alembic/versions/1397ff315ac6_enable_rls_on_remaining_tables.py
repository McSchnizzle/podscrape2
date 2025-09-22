"""enable_rls_on_remaining_tables

Revision ID: 1397ff315ac6
Revises: 2958951096e0
Create Date: 2025-09-22 04:48:24.073920

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1397ff315ac6'
down_revision: Union[str, Sequence[str], None] = '2958951096e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Enable RLS on remaining unrestricted tables with appropriate policies."""

    # Tables that need RLS enabled (skip alembic_version as it's managed by Alembic)
    tables = [
        'digest_episode_links',
        'pipeline_runs',
        'topic_instruction_versions',
        'topics'
    ]

    for table_name in tables:
        # Enable RLS on table
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;")

        # Create policy for service role (full access for backend operations)
        op.execute(f"""
            CREATE POLICY "service_role_policy" ON {table_name}
            FOR ALL TO service_role
            USING (true)
            WITH CHECK (true);
        """)

        # Create policy for authenticated users (read-only access for web UI)
        op.execute(f"""
            CREATE POLICY "authenticated_read_policy" ON {table_name}
            FOR SELECT TO authenticated
            USING (true);
        """)

    # Note: alembic_version table is intentionally left unrestricted
    # as it's managed by Alembic migration system


def downgrade() -> None:
    """Disable RLS on tables."""

    tables = [
        'digest_episode_links',
        'pipeline_runs',
        'topic_instruction_versions',
        'topics'
    ]

    for table_name in tables:
        # Drop policies first
        op.execute(f'DROP POLICY IF EXISTS "service_role_policy" ON {table_name};')
        op.execute(f'DROP POLICY IF EXISTS "authenticated_read_policy" ON {table_name};')

        # Disable RLS
        op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY;")
