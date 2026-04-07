"""Add dedup pre-dedupe storage, feed priority, and update feeds view

Revision ID: i5d6e7f8g9h0
Revises: h4c5d6e7f8g9
Create Date: 2026-04-07 09:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'i5d6e7f8g9h0'
down_revision = 'h4c5d6e7f8g9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Part A: store the pre-dedupe script content for audit / rollback
    op.add_column(
        'digests',
        sa.Column('script_content_predupe', sa.Text(), nullable=True),
    )

    # Part C: feed priority for sortable ordering (lower = higher priority)
    op.add_column(
        'feeds',
        sa.Column('priority', sa.Integer(), nullable=False, server_default='100'),
    )
    op.create_index('ix_feeds_priority', 'feeds', ['priority'])

    # Seed sparse priorities (100, 200, 300...) based on existing id order so
    # reordering via drag-and-drop rarely needs full renumber.
    op.execute("""
        WITH ranked AS (
            SELECT id, ROW_NUMBER() OVER (ORDER BY id) * 100 AS new_priority
            FROM feeds
        )
        UPDATE feeds f
        SET priority = ranked.new_priority
        FROM ranked
        WHERE f.id = ranked.id;
    """)

    # Update the feeds_with_latest_episode view to include feed_type and priority
    op.execute('DROP VIEW IF EXISTS feeds_with_latest_episode;')
    op.execute('''
        CREATE OR REPLACE VIEW feeds_with_latest_episode AS
        SELECT
            f.id,
            f.feed_url,
            f.feed_type,
            f.title,
            f.description,
            f.active,
            f.priority,
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
        ORDER BY f.priority ASC, f.id ASC;
    ''')


def downgrade() -> None:
    op.execute('DROP VIEW IF EXISTS feeds_with_latest_episode;')
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

    op.drop_index('ix_feeds_priority', table_name='feeds')
    op.drop_column('feeds', 'priority')
    op.drop_column('digests', 'script_content_predupe')
