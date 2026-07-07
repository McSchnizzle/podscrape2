"""Add story_arcs, story_arc_events, and story_arc_coverage tables

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-02-20 09:30:00.000000

On Supabase, story_arcs and story_arc_events were created via
supabase_schema.sql. This migration creates them with IF NOT EXISTS so the
chain is self-contained on local Postgres, then adds the
story_arc_coverage junction table.
"""
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
revision = 'f2a3b4c5d6e7'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create story_arcs table (was previously only in supabase_schema.sql)
    op.execute("""
        CREATE TABLE IF NOT EXISTS story_arcs (
            id SERIAL NOT NULL,
            arc_name VARCHAR(512) NOT NULL,
            arc_slug VARCHAR(255) NOT NULL UNIQUE,
            functional_category VARCHAR(50) NOT NULL DEFAULT 'other',
            digest_topic VARCHAR(256) NOT NULL,
            summary TEXT,
            started_at TIMESTAMP WITH TIME ZONE NOT NULL,
            last_updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
            event_count INTEGER NOT NULL DEFAULT 1,
            source_count INTEGER NOT NULL DEFAULT 1,
            included_in_digest_id INTEGER,
            included_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            PRIMARY KEY (id)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_story_arcs_digest_topic ON story_arcs (digest_topic);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_story_arcs_category ON story_arcs (functional_category);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_story_arcs_last_updated ON story_arcs (last_updated_at);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_story_arcs_slug ON story_arcs (arc_slug);")

    # Create story_arc_events table (was previously only in supabase_schema.sql)
    op.execute("""
        CREATE TABLE IF NOT EXISTS story_arc_events (
            id SERIAL NOT NULL,
            story_arc_id INTEGER NOT NULL REFERENCES story_arcs(id) ON DELETE CASCADE,
            event_date TIMESTAMP WITH TIME ZONE NOT NULL,
            event_summary TEXT NOT NULL,
            key_points TEXT[] NOT NULL DEFAULT '{}',
            source_feed_id INTEGER REFERENCES feeds(id) ON DELETE SET NULL,
            source_episode_id INTEGER REFERENCES episodes(id) ON DELETE SET NULL,
            source_episode_guid VARCHAR(512),
            source_name VARCHAR(256),
            perspective VARCHAR(50),
            relevance_score DOUBLE PRECISION,
            extracted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            PRIMARY KEY (id)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_story_arc_events_arc_id ON story_arc_events (story_arc_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_story_arc_events_date ON story_arc_events (event_date);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_story_arc_events_episode ON story_arc_events (source_episode_id);")

    # Create story_arc_coverage junction table
    op.create_table(
        'story_arc_coverage',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('story_arc_id', sa.Integer(), sa.ForeignKey('story_arcs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('digest_id', sa.Integer(), sa.ForeignKey('digests.id', ondelete='CASCADE'), nullable=False),
        sa.Column('covered_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    # Add unique constraint to prevent duplicate coverage records
    op.create_unique_constraint(
        'uq_story_arc_coverage_arc_digest',
        'story_arc_coverage',
        ['story_arc_id', 'digest_id']
    )

    # Add indexes for common queries
    op.create_index('ix_story_arc_coverage_arc_id', 'story_arc_coverage', ['story_arc_id'])
    op.create_index('ix_story_arc_coverage_digest_id', 'story_arc_coverage', ['digest_id'])
    op.create_index('ix_story_arc_coverage_covered_at', 'story_arc_coverage', ['covered_at'])

    # Enable RLS
    enable_rls("story_arc_coverage")
    create_service_role_policy("story_arc_coverage")
    create_authenticated_read_policy("story_arc_coverage")

    # Migrate existing included_in_digest_id data to the junction table
    op.execute('''
        INSERT INTO story_arc_coverage (story_arc_id, digest_id, covered_at)
        SELECT id, included_in_digest_id, COALESCE(included_at, now())
        FROM story_arcs
        WHERE included_in_digest_id IS NOT NULL;
    ''')


def downgrade() -> None:
    drop_policy("story_arc_coverage", "authenticated_read_policy")
    drop_policy("story_arc_coverage", "service_role_policy")
    op.drop_table('story_arc_coverage')

    op.execute('DROP TABLE IF EXISTS story_arc_events;')
    op.execute('DROP TABLE IF EXISTS story_arcs;')
