"""Add story_arc_coverage junction table for many-to-many arc-digest relationships

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-02-20 09:30:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f2a3b4c5d6e7'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade() -> None:
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
    op.execute("ALTER TABLE story_arc_coverage ENABLE ROW LEVEL SECURITY;")
    op.execute('''
        CREATE POLICY "service_role_policy" ON story_arc_coverage
        FOR ALL TO service_role
        USING (true) WITH CHECK (true);
    ''')
    op.execute('''
        CREATE POLICY "authenticated_read_policy" ON story_arc_coverage
        FOR SELECT TO authenticated
        USING (true);
    ''')

    # Migrate existing included_in_digest_id data to the junction table
    op.execute('''
        INSERT INTO story_arc_coverage (story_arc_id, digest_id, covered_at)
        SELECT id, included_in_digest_id, COALESCE(included_at, now())
        FROM story_arcs
        WHERE included_in_digest_id IS NOT NULL;
    ''')


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS "authenticated_read_policy" ON story_arc_coverage;')
    op.execute('DROP POLICY IF EXISTS "service_role_policy" ON story_arc_coverage;')
    op.drop_table('story_arc_coverage')
