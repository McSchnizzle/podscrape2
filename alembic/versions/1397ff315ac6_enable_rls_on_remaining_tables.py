"""enable_rls_on_remaining_tables

Revision ID: 1397ff315ac6
Revises: 2958951096e0
Create Date: 2025-09-22 04:48:24.073920

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from src.migration_rls import (
    enable_rls,
    create_service_role_policy,
    create_authenticated_read_policy,
    drop_policy,
    disable_rls,
)


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
        enable_rls(table_name)
        create_service_role_policy(table_name)
        create_authenticated_read_policy(table_name)

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
        drop_policy(table_name, "service_role_policy")
        drop_policy(table_name, "authenticated_read_policy")
        disable_rls(table_name)
