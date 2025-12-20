"""add_feeds_with_latest_episode_view

Revision ID: 3cb98f7a9984
Revises: 199afb551ab0
Create Date: 2025-12-20 01:53:07.480459

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3cb98f7a9984'
down_revision: Union[str, Sequence[str], None] = '199afb551ab0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create feeds_with_latest_episode view using LATERAL JOIN for O(1) query.

    This view eliminates N+1 queries in the getFeeds() method by pre-joining
    the latest episode data for each feed in a single efficient query.
    """
    op.execute('''
        CREATE OR REPLACE VIEW feeds_with_latest_episode AS
        SELECT
            f.id,
            f.feed_url,
            f.title,
            f.description,
            f.active,
            f.consecutive_failures,
            f.last_checked,
            f.total_episodes_processed,
            f.total_episodes_failed,
            f.created_at,
            f.updated_at,
            le.latest_episode_title,
            le.last_episode_date
        FROM feeds f
        LEFT JOIN LATERAL (
            SELECT
                e.title AS latest_episode_title,
                e.published_date AS last_episode_date
            FROM episodes e
            WHERE e.feed_id = f.id
            ORDER BY e.published_date DESC
            LIMIT 1
        ) le ON true
        ORDER BY f.created_at DESC;
    ''')

    # Note: Views inherit RLS from underlying tables when accessed via service role.
    # No additional RLS policy needed for the view itself since it's read-only
    # and pulls from feeds/episodes which already have RLS.


def downgrade() -> None:
    """Drop feeds_with_latest_episode view."""
    op.execute('DROP VIEW IF EXISTS feeds_with_latest_episode;')
