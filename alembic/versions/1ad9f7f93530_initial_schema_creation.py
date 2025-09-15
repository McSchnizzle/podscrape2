"""Initial schema creation

Revision ID: 1ad9f7f93530
Revises: 
Create Date: 2025-09-14 20:35:26.973951

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '1ad9f7f93530'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create feeds table
    op.create_table(
        'feeds',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('feed_url', sa.String(length=2048), nullable=False),
        sa.Column('title', sa.String(length=512), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('active', sa.Boolean(), nullable=False, default=True),
        sa.Column('consecutive_failures', sa.Integer(), nullable=False, default=0),
        sa.Column('last_checked', sa.DateTime(timezone=False)),
        sa.Column('last_episode_date', sa.DateTime(timezone=False)),
        sa.Column('total_episodes_processed', sa.Integer(), nullable=False, default=0),
        sa.Column('total_episodes_failed', sa.Integer(), nullable=False, default=0),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('feed_url')
    )
    op.create_index('ix_feeds_active', 'feeds', ['active'])

    # Create episodes table
    op.create_table(
        'episodes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('episode_guid', sa.String(length=1024), nullable=False),
        sa.Column('feed_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=1024), nullable=False),
        sa.Column('published_date', sa.DateTime(timezone=False), nullable=False),
        sa.Column('audio_url', sa.String(length=4096), nullable=False),
        sa.Column('duration_seconds', sa.Integer()),
        sa.Column('description', sa.Text()),
        sa.Column('audio_path', sa.String(length=4096)),
        sa.Column('audio_downloaded_at', sa.DateTime(timezone=False)),
        sa.Column('transcript_path', sa.String(length=4096)),
        sa.Column('transcript_generated_at', sa.DateTime(timezone=False)),
        sa.Column('transcript_word_count', sa.Integer()),
        sa.Column('chunk_count', sa.Integer(), nullable=False, default=0),
        sa.Column('scores', JSONB()),
        sa.Column('scored_at', sa.DateTime(timezone=False)),
        sa.Column('status', sa.String(length=64), nullable=False, default='pending'),
        sa.Column('failure_count', sa.Integer(), nullable=False, default=0),
        sa.Column('failure_reason', sa.Text()),
        sa.Column('last_failure_at', sa.DateTime(timezone=False)),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('episode_guid')
    )
    op.create_index('ix_episodes_status_published', 'episodes', ['status', 'published_date'])
    op.create_index('ix_episodes_scored', 'episodes', ['scored_at'])

    # Create digests table
    op.create_table(
        'digests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('topic', sa.String(length=256), nullable=False),
        sa.Column('digest_date', sa.Date(), nullable=False),
        sa.Column('script_path', sa.String(length=4096)),
        sa.Column('script_word_count', sa.Integer()),
        sa.Column('mp3_path', sa.String(length=4096)),
        sa.Column('mp3_duration_seconds', sa.Integer()),
        sa.Column('mp3_title', sa.String(length=1024)),
        sa.Column('mp3_summary', sa.Text()),
        sa.Column('episode_ids', JSONB()),
        sa.Column('episode_count', sa.Integer(), nullable=False, default=0),
        sa.Column('average_score', sa.Integer()),
        sa.Column('github_url', sa.String(length=4096)),
        sa.Column('published_at', sa.DateTime(timezone=False)),
        sa.Column('generated_at', sa.DateTime(timezone=False)),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_digests_date', 'digests', ['digest_date'])
    op.create_index(None, 'digests', ['topic', 'digest_date'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_digests_date', 'digests')
    op.drop_index(None, 'digests')  # unique constraint index
    op.drop_table('digests')

    op.drop_index('ix_episodes_scored', 'episodes')
    op.drop_index('ix_episodes_status_published', 'episodes')
    op.drop_table('episodes')

    op.drop_index('ix_feeds_active', 'feeds')
    op.drop_table('feeds')
