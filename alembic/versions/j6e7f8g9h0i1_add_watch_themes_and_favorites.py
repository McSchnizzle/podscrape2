"""Add watch_themes table and favorite flag on digests

Revision ID: j6e7f8g9h0i1
Revises: i5d6e7f8g9h0
Create Date: 2026-04-17 16:00:00.000000

Two additions:
1. watch_themes: user-curated natural-language themes for personal weekly
   digest (the Watch Themes feature). Each active theme is scanned weekly
   against AI&Tech transcripts to produce a personal HTML digest.
2. digests.is_favorite: flag to exempt specific digests from retention cleanup
   (MP3 deletion, GitHub release cleanup, local file removal). Favorites are
   preserved indefinitely.
"""
from alembic import op
import sqlalchemy as sa


revision = 'j6e7f8g9h0i1'
down_revision = 'i5d6e7f8g9h0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # watch_themes ---------------------------------------------------------
    op.create_table(
        'watch_themes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_watch_themes_active', 'watch_themes', ['active'])
    op.create_index('ix_watch_themes_sort_order', 'watch_themes', ['sort_order'])

    # RLS on watch_themes — service_role bypass per project convention
    op.execute("ALTER TABLE watch_themes ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY watch_themes_service_all ON watch_themes "
        "FOR ALL TO service_role USING (true) WITH CHECK (true)"
    )

    # digests.is_favorite --------------------------------------------------
    op.add_column(
        'digests',
        sa.Column('is_favorite', sa.Boolean(),
                  nullable=False, server_default='false'),
    )
    op.create_index(
        'ix_digests_is_favorite', 'digests', ['is_favorite'],
        postgresql_where=sa.text('is_favorite = true'),
    )

    # watch_digest_runs — audit/replay table for weekly runs --------------
    op.create_table(
        'watch_digest_runs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('run_date', sa.Date(), nullable=False),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('window_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('themes_scanned', sa.Integer(), nullable=False),
        sa.Column('episodes_scanned', sa.Integer(), nullable=False),
        sa.Column('html_content', sa.Text(), nullable=True),
        sa.Column('markdown_content', sa.Text(), nullable=True),
        sa.Column('email_delivered', sa.Boolean(),
                  nullable=False, server_default='false'),
        sa.Column('harold_delivered', sa.Boolean(),
                  nullable=False, server_default='false'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('run_date', name='uq_watch_digest_runs_run_date'),
    )
    op.execute("ALTER TABLE watch_digest_runs ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY watch_digest_runs_service_all ON watch_digest_runs "
        "FOR ALL TO service_role USING (true) WITH CHECK (true)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS watch_digest_runs_service_all ON watch_digest_runs")
    op.drop_table('watch_digest_runs')

    op.drop_index('ix_digests_is_favorite', table_name='digests')
    op.drop_column('digests', 'is_favorite')

    op.execute("DROP POLICY IF EXISTS watch_themes_service_all ON watch_themes")
    op.drop_index('ix_watch_themes_sort_order', table_name='watch_themes')
    op.drop_index('ix_watch_themes_active', table_name='watch_themes')
    op.drop_table('watch_themes')
