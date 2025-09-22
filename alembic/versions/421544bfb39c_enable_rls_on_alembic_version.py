"""enable_rls_on_alembic_version

Revision ID: 421544bfb39c
Revises: 1397ff315ac6
Create Date: 2025-09-22 04:51:01.615214

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '421544bfb39c'
down_revision: Union[str, Sequence[str], None] = '1397ff315ac6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Enable RLS on alembic_version table with service role access only."""

    # Enable RLS on alembic_version table
    op.execute("ALTER TABLE alembic_version ENABLE ROW LEVEL SECURITY;")

    # Create policy for service role (Alembic migrations need full access)
    op.execute("""
        CREATE POLICY "service_role_policy" ON alembic_version
        FOR ALL TO service_role
        USING (true)
        WITH CHECK (true);
    """)

    # Note: No authenticated user policy - this table should only be accessed by migrations


def downgrade() -> None:
    """Disable RLS on alembic_version table."""

    # Drop policy first
    op.execute('DROP POLICY IF EXISTS "service_role_policy" ON alembic_version;')

    # Disable RLS
    op.execute("ALTER TABLE alembic_version DISABLE ROW LEVEL SECURITY;")
