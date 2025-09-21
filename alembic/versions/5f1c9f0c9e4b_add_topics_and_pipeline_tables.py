"""Add topics, digest episode links, and pipeline run tables

Revision ID: 5f1c9f0c9e4b
Revises: 3062e0ca95ee
Create Date: 2025-09-20 12:34:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '5f1c9f0c9e4b'
down_revision: Union[str, Sequence[str], None] = '3062e0ca95ee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'topics',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('voice_id', sa.String(length=255)),
        sa.Column('voice_settings', postgresql.JSONB(astext_type=sa.Text())),
        sa.Column('instructions_md', sa.Text()),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_generated_at', sa.DateTime(timezone=False)),
        sa.Column('created_at', sa.DateTime(timezone=False), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=False), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('slug', name='uq_topics_slug')
    )
    op.create_index('ix_topics_active', 'topics', ['is_active'])
    op.create_index('ix_topics_sort', 'topics', ['sort_order'])

    op.create_table(
        'topic_instruction_versions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('topic_id', sa.Integer(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('instructions_md', sa.Text(), nullable=False),
        sa.Column('change_note', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=False), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_by', sa.String(length=255)),
        sa.UniqueConstraint('topic_id', 'version', name='uq_topic_instruction_version')
    )
    op.create_index('ix_topic_instruction_topic', 'topic_instruction_versions', ['topic_id'])

    op.create_table(
        'pipeline_runs',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('workflow_run_id', sa.BigInteger()),
        sa.Column('workflow_name', sa.String(length=255)),
        sa.Column('trigger', sa.String(length=128)),
        sa.Column('status', sa.String(length=64)),
        sa.Column('conclusion', sa.String(length=64)),
        sa.Column('started_at', sa.DateTime(timezone=False)),
        sa.Column('finished_at', sa.DateTime(timezone=False)),
        sa.Column('phase', postgresql.JSONB(astext_type=sa.Text())),
        sa.Column('notes', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=False), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=False), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'))
    )
    op.create_index('ix_pipeline_runs_started', 'pipeline_runs', ['started_at'])
    op.create_index('ix_pipeline_runs_workflow', 'pipeline_runs', ['workflow_run_id'])

    op.create_table(
        'digest_episode_links',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('digest_id', sa.Integer(), nullable=False),
        sa.Column('episode_id', sa.Integer(), nullable=False),
        sa.Column('topic', sa.String(length=256)),
        sa.Column('score', sa.Float()),
        sa.Column('position', sa.Integer()),
        sa.Column('created_at', sa.DateTime(timezone=False), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('digest_id', 'episode_id', name='uq_digest_episode'),
    )
    op.create_index('ix_digest_episode_digest', 'digest_episode_links', ['digest_id'])
    op.create_index('ix_digest_episode_episode', 'digest_episode_links', ['episode_id'])


def downgrade() -> None:
    op.drop_index('ix_digest_episode_episode', table_name='digest_episode_links')
    op.drop_index('ix_digest_episode_digest', table_name='digest_episode_links')
    op.drop_table('digest_episode_links')

    op.drop_index('ix_pipeline_runs_workflow', table_name='pipeline_runs')
    op.drop_index('ix_pipeline_runs_started', table_name='pipeline_runs')
    op.drop_table('pipeline_runs')

    op.drop_index('ix_topic_instruction_topic', table_name='topic_instruction_versions')
    op.drop_table('topic_instruction_versions')

    op.drop_index('ix_topics_sort', table_name='topics')
    op.drop_index('ix_topics_active', table_name='topics')
    op.drop_table('topics')
