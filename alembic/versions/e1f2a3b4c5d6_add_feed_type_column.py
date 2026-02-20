"""Add feed_type column to feeds table for YouTube support

Revision ID: e1f2a3b4c5d6
Revises: b7878381e0ad
Create Date: 2026-02-20 08:30:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e1f2a3b4c5d6'
down_revision = 'b7878381e0ad'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add feed_type column with default 'rss'
    op.add_column('feeds', sa.Column('feed_type', sa.String(50), nullable=False, server_default='rss'))

    # Set existing YouTube feeds based on URL pattern
    op.execute("""
        UPDATE feeds SET feed_type = 'youtube'
        WHERE feed_url LIKE '%youtube.com%'
           OR feed_url LIKE '%youtu.be%'
    """)

    # Add index for feed_type queries
    op.create_index('ix_feeds_feed_type', 'feeds', ['feed_type'])


def downgrade() -> None:
    op.drop_index('ix_feeds_feed_type', table_name='feeds')
    op.drop_column('feeds', 'feed_type')
