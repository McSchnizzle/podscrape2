"""Enable RLS on web_settings table

Revision ID: 3062e0ca95ee
Revises: 1ad9f7f93530
Create Date: 2025-09-15 10:29:06.765220

"""
from typing import Sequence, Union

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
revision: str = '3062e0ca95ee'
down_revision: Union[str, Sequence[str], None] = '1ad9f7f93530'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create web_settings table (if missing) and enable RLS."""

    # On Supabase this table was created out-of-band via supabase_schema.sql.
    # On local Postgres we create it here so the migration chain is self-contained.
    op.execute("""
        CREATE TABLE IF NOT EXISTS web_settings (
            id SERIAL NOT NULL,
            category VARCHAR(128) NOT NULL,
            setting_key VARCHAR(128) NOT NULL,
            setting_value TEXT NOT NULL,
            value_type VARCHAR(32) DEFAULT 'string',
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_web_settings_category_key UNIQUE (category, setting_key),
            PRIMARY KEY (id)
        );
    """)

    # Enable RLS on web_settings table
    enable_rls("web_settings")

    # Create policy for service role (full access)
    create_service_role_policy("web_settings")

    # Create policy for authenticated users (read-only by default)
    create_authenticated_read_policy("web_settings")


def downgrade() -> None:
    """Disable RLS on web_settings table."""

    # Drop policies first
    drop_policy("web_settings", "service_role_policy")
    drop_policy("web_settings", "authenticated_read_policy")

    # Disable RLS
    disable_rls("web_settings")
