"""Enable RLS on web_settings table

Revision ID: 3062e0ca95ee
Revises: 1ad9f7f93530
Create Date: 2025-09-15 10:29:06.765220

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3062e0ca95ee'
down_revision: Union[str, Sequence[str], None] = '1ad9f7f93530'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Enable RLS on web_settings table with appropriate policies."""

    # Enable RLS on web_settings table
    op.execute("ALTER TABLE web_settings ENABLE ROW LEVEL SECURITY;")

    # Create policy for service role (full access)
    op.execute("""
        CREATE POLICY "service_role_policy" ON web_settings
        FOR ALL TO service_role
        USING (true)
        WITH CHECK (true);
    """)

    # Create policy for authenticated users (read-only by default)
    op.execute("""
        CREATE POLICY "authenticated_read_policy" ON web_settings
        FOR SELECT TO authenticated
        USING (true);
    """)


def downgrade() -> None:
    """Disable RLS on web_settings table."""

    # Drop policies first
    op.execute('DROP POLICY IF EXISTS "service_role_policy" ON web_settings;')
    op.execute('DROP POLICY IF EXISTS "authenticated_read_policy" ON web_settings;')

    # Disable RLS
    op.execute("ALTER TABLE web_settings DISABLE ROW LEVEL SECURITY;")
