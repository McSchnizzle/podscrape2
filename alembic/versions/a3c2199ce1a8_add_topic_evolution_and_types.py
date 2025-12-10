"""add_topic_evolution_and_types

Revision ID: a3c2199ce1a8
Revises: d8f9e2a7b5c4
Create Date: 2025-12-10 14:05:14.649037

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3c2199ce1a8'
down_revision: Union[str, Sequence[str], None] = 'd8f9e2a7b5c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Add topic evolution and type classification fields."""
    # Add new columns to episode_topics table (all nullable initially for backward compatibility)
    op.add_column('episode_topics', sa.Column('topic_type', sa.String(50), nullable=True))
    op.add_column('episode_topics', sa.Column('novelty_score', sa.Float, nullable=True))
    op.add_column('episode_topics', sa.Column('is_update', sa.Boolean, nullable=True))
    op.add_column('episode_topics', sa.Column('parent_topic_id', sa.Integer, nullable=True))
    op.add_column('episode_topics', sa.Column('evolution_summary', sa.Text, nullable=True))
    op.add_column('episode_topics', sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=True))

    # Add foreign key constraint for parent_topic_id
    op.create_foreign_key(
        'fk_episode_topics_parent',
        'episode_topics', 'episode_topics',
        ['parent_topic_id'], ['id'],
        ondelete='SET NULL'
    )

    # Set defaults for existing records
    op.execute("UPDATE episode_topics SET topic_type = 'other' WHERE topic_type IS NULL")
    op.execute("UPDATE episode_topics SET novelty_score = 1.0 WHERE novelty_score IS NULL")
    op.execute("UPDATE episode_topics SET is_update = FALSE WHERE is_update IS NULL")
    op.execute("UPDATE episode_topics SET first_seen_at = created_at WHERE first_seen_at IS NULL")

    # Enable RLS on episode_topics (if not already enabled)
    op.execute("ALTER TABLE episode_topics ENABLE ROW LEVEL SECURITY;")

    # Create RLS policies for episode_topics (if not exist)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                WHERE tablename = 'episode_topics' AND policyname = 'service_role_policy'
            ) THEN
                CREATE POLICY "service_role_policy" ON episode_topics
                FOR ALL TO service_role
                USING (true) WITH CHECK (true);
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    """Downgrade schema: Remove topic evolution fields."""
    # Drop foreign key constraint
    op.drop_constraint('fk_episode_topics_parent', 'episode_topics', type_='foreignkey')

    # Drop columns
    op.drop_column('episode_topics', 'first_seen_at')
    op.drop_column('episode_topics', 'evolution_summary')
    op.drop_column('episode_topics', 'parent_topic_id')
    op.drop_column('episode_topics', 'is_update')
    op.drop_column('episode_topics', 'novelty_score')
    op.drop_column('episode_topics', 'topic_type')
