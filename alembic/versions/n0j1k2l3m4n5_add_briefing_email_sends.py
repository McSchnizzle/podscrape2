"""Add briefing_email_sends for the Phase 8 creator briefing email

Ledger of nightly story-briefing emails, so a digest is mailed to a recipient
at most once even if the pipeline re-runs. Preview sends are kept with
is_test = true and do not block the real send.

Revision ID: n0j1k2l3m4n5
Revises: m9i0j1k2l3m4
Create Date: 2026-09-26
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'n0j1k2l3m4n5'
down_revision = 'm9i0j1k2l3m4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if 'briefing_email_sends' in sa.inspect(bind).get_table_names():
        return

    op.create_table(
        'briefing_email_sends',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('digest_id', sa.Integer(), sa.ForeignKey('digests.id', ondelete='CASCADE'), nullable=False),
        sa.Column('recipient', sa.String(320), nullable=False),
        sa.Column('subject', sa.Text(), nullable=False),
        sa.Column('message_id', sa.String(255)),
        sa.Column('story_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_test', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_briefing_email_sends_digest_recipient', 'briefing_email_sends',
                    ['digest_id', 'recipient'])

    # RLS in the same migration (docs/database-rls.md).
    op.execute("ALTER TABLE briefing_email_sends ENABLE ROW LEVEL SECURITY;")
    op.execute('''
        CREATE POLICY "service_role_policy" ON briefing_email_sends
        FOR ALL TO service_role
        USING (true) WITH CHECK (true);
    ''')
    op.execute('''
        CREATE POLICY "authenticated_read_policy" ON briefing_email_sends
        FOR SELECT TO authenticated
        USING (true);
    ''')


def downgrade() -> None:
    op.drop_index('ix_briefing_email_sends_digest_recipient', table_name='briefing_email_sends')
    op.drop_table('briefing_email_sends')
