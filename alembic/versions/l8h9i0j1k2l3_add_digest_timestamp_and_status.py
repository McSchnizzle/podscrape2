"""Add missing digests.digest_timestamp + digests.status; fix unique constraint

The Digest model has carried digest_timestamp (NOT NULL, part of the
uq_digests_topic_date_timestamp unique constraint) and status since the
Supabase era, but no migration ever created them -- the old database got them
out-of-band. On the locally rebuilt database (kanban #2669) the drift made the
digest phase fail with UndefinedColumn on 2026-07-08, and the stricter
(topic, digest_date) unique index would have rejected legitimate same-day
regenerations the model explicitly allows.

Revision ID: l8h9i0j1k2l3
Revises: k7f8g9h0i1j2
Create Date: 2026-07-08
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'l8h9i0j1k2l3'
down_revision = 'k7f8g9h0i1j2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c['name'] for c in insp.get_columns('digests')}

    if 'digest_timestamp' not in cols:
        op.add_column(
            'digests',
            sa.Column('digest_timestamp', sa.DateTime(timezone=False),
                      nullable=False, server_default=sa.text('now()')),
        )
        # Historical rows: the generation time is the best available value.
        op.execute(
            "UPDATE digests SET digest_timestamp = generated_at "
            "WHERE generated_at IS NOT NULL"
        )

    if 'status' not in cols:
        op.add_column('digests', sa.Column('status', sa.String(50),
                                           server_default='draft'))
        # Rows that already shipped (mp3 + GitHub release) are published.
        op.execute(
            "UPDATE digests SET status = 'published' "
            "WHERE github_url IS NOT NULL AND mp3_path IS NOT NULL"
        )

    # Replace the too-strict (topic, digest_date) unique index with the
    # model's (topic, digest_date, digest_timestamp) unique constraint.
    existing_indexes = {i['name'] for i in insp.get_indexes('digests')}
    existing_uniques = {c['name'] for c in insp.get_unique_constraints('digests')}
    if 'ix_digests_topic' in existing_indexes:
        op.drop_index('ix_digests_topic', table_name='digests')
    if 'uq_digests_topic_date_timestamp' not in existing_uniques:
        op.create_unique_constraint(
            'uq_digests_topic_date_timestamp', 'digests',
            ['topic', 'digest_date', 'digest_timestamp'],
        )
    if 'ix_digests_timestamp' not in existing_indexes:
        op.create_index('ix_digests_timestamp', 'digests', ['digest_timestamp'])


def downgrade() -> None:
    op.drop_constraint('uq_digests_topic_date_timestamp', 'digests', type_='unique')
    op.drop_index('ix_digests_timestamp', table_name='digests')
    op.create_index('ix_digests_topic', 'digests', ['topic', 'digest_date'], unique=True)
    op.drop_column('digests', 'status')
    op.drop_column('digests', 'digest_timestamp')
