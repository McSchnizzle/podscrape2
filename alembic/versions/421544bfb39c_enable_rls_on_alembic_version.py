"""enable_rls_on_alembic_version

Revision ID: 421544bfb39c
Revises: 1397ff315ac6
Create Date: 2025-09-22 04:51:01.615214

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from src.migration_rls import (
    enable_rls,
    create_service_role_policy,
    drop_policy,
    disable_rls,
)


# revision identifiers, used by Alembic.
revision: str = '421544bfb39c'
down_revision: Union[str, Sequence[str], None] = '1397ff315ac6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Enable RLS on alembic_version table with service role access only."""

    enable_rls("alembic_version")
    create_service_role_policy("alembic_version")


def downgrade() -> None:
    """Disable RLS on alembic_version table."""

    drop_policy("alembic_version", "service_role_policy")
    disable_rls("alembic_version")
