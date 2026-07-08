"""add_multi_voice_support_to_topics

Revision ID: 627ebea71c37
Revises: b2eebe8a3dcc
Create Date: 2025-11-10 15:50:16.951584

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from src.migration_rls import (
    enable_rls,
    create_service_role_policy,
    create_authenticated_read_policy,
)


# revision identifiers, used by Alembic.
revision: str = '627ebea71c37'
down_revision: Union[str, Sequence[str], None] = 'b2eebe8a3dcc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add columns for multi-voice dialogue support
    op.add_column('topics', sa.Column('use_dialogue_api', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('topics', sa.Column('dialogue_model', sa.String(50), nullable=False, server_default='eleven_turbo_v2_5'))
    op.add_column('topics', sa.Column('voice_config', sa.dialects.postgresql.JSONB(), nullable=True))

    # Enable RLS on topics (idempotent — already enabled by 1397ff315ac6, but
    # kept for safety when running on a fresh local DB that skips RLS).
    enable_rls("topics")

    # Service role policy (full access for backend operations)
    create_service_role_policy("topics")

    # Authenticated read policy (web UI access)
    create_authenticated_read_policy("topics")


def downgrade() -> None:
    """Downgrade schema."""
    # Remove added columns
    op.drop_column('topics', 'voice_config')
    op.drop_column('topics', 'dialogue_model')
    op.drop_column('topics', 'use_dialogue_api')
