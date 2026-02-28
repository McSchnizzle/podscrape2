"""Add hot story fields to story_arcs (is_hot, hot_briefing, retain_until)

Revision ID: h4c5d6e7f8g9
Revises: g3b4c5d6e7f8
Create Date: 2026-02-28 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'h4c5d6e7f8g9'
down_revision = 'g3b4c5d6e7f8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # is_hot: manually flagged by user for priority tracking
    op.add_column('story_arcs', sa.Column(
        'is_hot', sa.Boolean(), nullable=False, server_default='false'
    ))

    # hot_briefing: accumulated briefing document for hot stories
    op.add_column('story_arcs', sa.Column(
        'hot_briefing', sa.Text(), nullable=True
    ))

    # retain_until: overrides retention cleanup when set
    op.add_column('story_arcs', sa.Column(
        'retain_until', sa.DateTime(timezone=True), nullable=True
    ))

    # Index for quick hot story queries
    op.create_index('ix_story_arcs_is_hot', 'story_arcs', ['is_hot'],
                     postgresql_where=sa.text('is_hot = true'))


def downgrade() -> None:
    op.drop_index('ix_story_arcs_is_hot', table_name='story_arcs')
    op.drop_column('story_arcs', 'retain_until')
    op.drop_column('story_arcs', 'hot_briefing')
    op.drop_column('story_arcs', 'is_hot')
