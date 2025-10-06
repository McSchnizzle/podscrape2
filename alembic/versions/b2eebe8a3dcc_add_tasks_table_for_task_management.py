"""add_tasks_table_for_task_management

Revision ID: b2eebe8a3dcc
Revises: b5afb6170c33
Create Date: 2025-10-06 08:04:32.262154

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b2eebe8a3dcc'
down_revision: Union[str, Sequence[str], None] = 'b5afb6170c33'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create tasks table for task management system."""

    # Create tasks table
    op.create_table(
        'tasks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='open'),
        sa.Column('priority', sa.String(length=10), nullable=False, server_default='P3'),
        sa.Column('category', sa.String(length=100)),
        sa.Column('submission_date', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('last_update_date', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('version_introduced', sa.String(length=50)),
        sa.Column('version_completed', sa.String(length=50)),
        sa.Column('files_affected', postgresql.ARRAY(sa.Text())),
        sa.Column('completion_notes', sa.Text()),
        sa.Column('estimated_effort', sa.String(length=50)),
        sa.Column('session_number', sa.Integer()),
        sa.Column('tags', postgresql.ARRAY(sa.Text())),
        sa.Column('created_by', sa.String(length=255), server_default='brownpr0@gmail.com'),
        sa.Column('assigned_to', sa.String(length=255))
    )

    # Create indexes for efficient querying
    op.create_index('ix_tasks_status', 'tasks', ['status'])
    op.create_index('ix_tasks_priority', 'tasks', ['priority'])
    op.create_index('ix_tasks_category', 'tasks', ['category'])
    op.create_index('ix_tasks_submission_date', 'tasks', ['submission_date'], postgresql_ops={'submission_date': 'DESC'})
    op.create_index('ix_tasks_last_update_date', 'tasks', ['last_update_date'], postgresql_ops={'last_update_date': 'DESC'})

    # Enable RLS on tasks table
    op.execute("ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;")

    # Create policy for service role (full access for backend operations)
    op.execute("""
        CREATE POLICY "service_role_policy" ON tasks
        FOR ALL TO service_role
        USING (true)
        WITH CHECK (true);
    """)

    # Create policy for authenticated users (full access for web UI)
    op.execute("""
        CREATE POLICY "authenticated_users_policy" ON tasks
        FOR ALL TO authenticated
        USING (true)
        WITH CHECK (true);
    """)


def downgrade() -> None:
    """Drop tasks table and related objects."""

    # Drop policies first
    op.execute('DROP POLICY IF EXISTS "service_role_policy" ON tasks;')
    op.execute('DROP POLICY IF EXISTS "authenticated_users_policy" ON tasks;')

    # Disable RLS
    op.execute("ALTER TABLE tasks DISABLE ROW LEVEL SECURITY;")

    # Drop indexes
    op.drop_index('ix_tasks_last_update_date', table_name='tasks')
    op.drop_index('ix_tasks_submission_date', table_name='tasks')
    op.drop_index('ix_tasks_category', table_name='tasks')
    op.drop_index('ix_tasks_priority', table_name='tasks')
    op.drop_index('ix_tasks_status', table_name='tasks')

    # Drop table
    op.drop_table('tasks')
