"""add_workflow_errors_table

Revision ID: c4d5e6f7a8b9
Revises: a3c2199ce1a8
Create Date: 2025-12-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'a3c2199ce1a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create workflow_errors table with indexes and RLS."""
    op.create_table(
        'workflow_errors',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('error_date', sa.Date(), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('run_id', sa.String(128), nullable=False),
        sa.Column('workflow_run_id', sa.Integer(), nullable=True),
        sa.Column('error_category', sa.String(64), nullable=False),
        sa.Column('phase', sa.String(64), nullable=False),
        sa.Column('severity', sa.String(16), nullable=False, server_default='error'),
        sa.Column('feed_id', sa.Integer(), nullable=True),
        sa.Column('feed_url', sa.String(2048), nullable=True),
        sa.Column('error_code', sa.String(32), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=False),
        sa.Column('error_summary', sa.String(512), nullable=True),
        sa.Column('extra', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('source_log_id', sa.Integer(), nullable=True),
        sa.Column('resolved', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    # Indexes for common query patterns
    op.create_index('ix_workflow_errors_date', 'workflow_errors', ['error_date'])
    op.create_index('ix_workflow_errors_run_id', 'workflow_errors', ['run_id'])
    op.create_index('ix_workflow_errors_category', 'workflow_errors', ['error_category'])
    op.create_index('ix_workflow_errors_phase', 'workflow_errors', ['phase'])
    op.create_index('ix_workflow_errors_feed_id', 'workflow_errors', ['feed_id'])
    op.create_index('ix_workflow_errors_category_date', 'workflow_errors',
                    ['error_category', 'error_date'])
    op.create_index('ix_workflow_errors_feed_category', 'workflow_errors',
                    ['feed_id', 'error_category'])

    # RLS policies (required per project standards)
    op.execute("ALTER TABLE workflow_errors ENABLE ROW LEVEL SECURITY;")
    op.execute('''
        CREATE POLICY "service_role_policy" ON workflow_errors
        FOR ALL TO service_role
        USING (true) WITH CHECK (true);
    ''')
    op.execute('''
        CREATE POLICY "authenticated_read_policy" ON workflow_errors
        FOR SELECT TO authenticated
        USING (true);
    ''')


def downgrade() -> None:
    """Drop workflow_errors table."""
    op.execute('DROP POLICY IF EXISTS "authenticated_read_policy" ON workflow_errors;')
    op.execute('DROP POLICY IF EXISTS "service_role_policy" ON workflow_errors;')

    op.drop_index('ix_workflow_errors_feed_category', table_name='workflow_errors')
    op.drop_index('ix_workflow_errors_category_date', table_name='workflow_errors')
    op.drop_index('ix_workflow_errors_feed_id', table_name='workflow_errors')
    op.drop_index('ix_workflow_errors_phase', table_name='workflow_errors')
    op.drop_index('ix_workflow_errors_category', table_name='workflow_errors')
    op.drop_index('ix_workflow_errors_run_id', table_name='workflow_errors')
    op.drop_index('ix_workflow_errors_date', table_name='workflow_errors')

    op.drop_table('workflow_errors')
