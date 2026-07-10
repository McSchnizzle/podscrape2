"""Add watch_themes.scope for daily-emphasis targeting

The 4 original watch themes were implicitly weekly-only (Sunday digest via
run_watch_digest.py). Paul wants some themes to ALSO (or ONLY) shape nightly
show generation -- e.g. an "AI standards, governance, and industry
consortiums" theme that should surface in the daily AI & Technology digest
whenever it matches, not just the Sunday roundup.

'scope' distinguishes:
  - 'weekly' (default): scanned only by the Sunday watch-digest.
  - 'daily': scanned only by nightly digest generation (Tier B emphasis).
  - 'both': scanned by both pipelines independently.

Revision ID: m9i0j1k2l3m4
Revises: l8h9i0j1k2l3
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'm9i0j1k2l3m4'
down_revision = 'l8h9i0j1k2l3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c['name'] for c in insp.get_columns('watch_themes')}

    if 'scope' not in cols:
        op.add_column(
            'watch_themes',
            sa.Column('scope', sa.String(16), nullable=False, server_default='weekly'),
        )

    existing_indexes = {i['name'] for i in insp.get_indexes('watch_themes')}
    if 'ix_watch_themes_scope' not in existing_indexes:
        op.create_index('ix_watch_themes_scope', 'watch_themes', ['scope'])

    existing_checks = {c['name'] for c in insp.get_check_constraints('watch_themes')}
    if 'ck_watch_themes_scope' not in existing_checks:
        op.create_check_constraint(
            'ck_watch_themes_scope', 'watch_themes',
            "scope IN ('weekly', 'daily', 'both')",
        )


def downgrade() -> None:
    op.drop_constraint('ck_watch_themes_scope', 'watch_themes', type_='check')
    op.drop_index('ix_watch_themes_scope', table_name='watch_themes')
    op.drop_column('watch_themes', 'scope')
