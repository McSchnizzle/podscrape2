"""add_topic_tracking_and_ad_filtering

Revision ID: d8f9e2a7b5c4
Revises: 627ebea71c37
Create Date: 2025-12-10 16:00:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from src.migration_rls import (
    enable_rls,
    create_service_role_policy,
    create_authenticated_read_policy,
)

# revision identifiers, used by Alembic.
revision: str = 'd8f9e2a7b5c4'
down_revision: Union[str, Sequence[str], None] = '627ebea71c37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create episode_topics table
    op.create_table(
        'episode_topics',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('episode_id', sa.Integer(), nullable=False),
        sa.Column('topic_name', sa.String(512), nullable=False),
        sa.Column('topic_slug', sa.String(255), nullable=False),
        sa.Column('key_points', postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column('first_mentioned_at', sa.DateTime(timezone=False), nullable=False),
        sa.Column('last_mentioned_at', sa.DateTime(timezone=False), nullable=False),
        sa.Column('mention_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('digest_topic', sa.String(256), nullable=False),
        sa.Column('relevance_score', sa.Float()),
        sa.Column('included_in_digest_id', sa.Integer()),
        sa.Column('included_at', sa.DateTime(timezone=False)),
        sa.Column('created_at', sa.DateTime(timezone=False), nullable=False,
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=False), nullable=False,
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['episode_id'], ['episodes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['included_in_digest_id'], ['digests.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('episode_id', 'topic_slug', name='uq_episode_topics_episode_slug')
    )

    # Create indexes for episode_topics
    op.create_index('ix_episode_topics_episode', 'episode_topics', ['episode_id'])
    op.create_index('ix_episode_topics_slug', 'episode_topics', ['topic_slug'])
    op.create_index('ix_episode_topics_digest_topic', 'episode_topics', ['digest_topic'])
    op.create_index('ix_episode_topics_included', 'episode_topics', ['included_in_digest_id'])
    op.create_index('ix_episode_topics_mentioned', 'episode_topics', ['last_mentioned_at'])

    # Enable RLS on episode_topics
    enable_rls("episode_topics")
    create_service_role_policy("episode_topics")
    create_authenticated_read_policy("episode_topics")

    # Create common_ads table
    op.create_table(
        'common_ads',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('advertiser_name', sa.String(256), nullable=False, unique=True),
        sa.Column('pattern_keywords', postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column('confidence_threshold', sa.Float(), nullable=False, server_default='0.8'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('first_detected_at', sa.DateTime(timezone=False), nullable=False,
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('last_detected_at', sa.DateTime(timezone=False), nullable=False,
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('detection_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=False), nullable=False,
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=False), nullable=False,
                  server_default=sa.text('CURRENT_TIMESTAMP'))
    )

    # Create indexes for common_ads
    op.create_index('ix_common_ads_active', 'common_ads', ['is_active'])
    op.create_index('ix_common_ads_advertiser', 'common_ads', ['advertiser_name'])

    # Enable RLS on common_ads
    enable_rls("common_ads")
    create_service_role_policy("common_ads")
    create_authenticated_read_policy("common_ads")

    # Seed initial ad patterns
    op.execute("""
        INSERT INTO common_ads (advertiser_name, pattern_keywords, confidence_threshold, is_active)
        VALUES
            ('KPMG', ARRAY['kpmg', 'visit kpmg.com', 'kpmg.com'], 0.7, true),
            ('Robots and Pencils', ARRAY['robots and pencils', 'robotsandpencils.com'], 0.8, true),
            ('Blitzy', ARRAY['blitzy', 'visit blitzy', 'blitzy.com'], 0.8, true)
        ON CONFLICT (advertiser_name) DO NOTHING;
    """)

    # Add enable_topic_tracking column to topics table
    op.add_column('topics', sa.Column('enable_topic_tracking', sa.Boolean(), nullable=False, server_default='false'))

    # Enable topic tracking for AI and Technology topic
    op.execute("""
        UPDATE topics
        SET enable_topic_tracking = true
        WHERE slug = 'ai-and-technology' OR name ILIKE '%AI%Technology%';
    """)


def downgrade() -> None:
    # Remove enable_topic_tracking column from topics
    op.drop_column('topics', 'enable_topic_tracking')

    # Drop RLS policies for common_ads
    from src.migration_rls import drop_policy, disable_rls
    drop_policy("common_ads", "service_role_policy")
    drop_policy("common_ads", "authenticated_read_policy")
    disable_rls("common_ads")

    # Drop common_ads table
    op.drop_index('ix_common_ads_advertiser', table_name='common_ads')
    op.drop_index('ix_common_ads_active', table_name='common_ads')
    op.drop_table('common_ads')

    # Drop RLS policies for episode_topics
    drop_policy("episode_topics", "service_role_policy")
    drop_policy("episode_topics", "authenticated_read_policy")
    disable_rls("episode_topics")

    # Drop indexes for episode_topics
    op.drop_index('ix_episode_topics_mentioned', table_name='episode_topics')
    op.drop_index('ix_episode_topics_included', table_name='episode_topics')
    op.drop_index('ix_episode_topics_digest_topic', table_name='episode_topics')
    op.drop_index('ix_episode_topics_slug', table_name='episode_topics')
    op.drop_index('ix_episode_topics_episode', table_name='episode_topics')

    # Drop episode_topics table
    op.drop_table('episode_topics')
