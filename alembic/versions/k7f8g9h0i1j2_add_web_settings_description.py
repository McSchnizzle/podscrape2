"""Add missing description column to web_settings

Revision ID: k7f8g9h0i1j2
Revises: j6e7f8g9h0i1
Create Date: 2026-07-07 17:45:00.000000

The local Postgres rebuild path creates web_settings in migration
3062e0ca95ee, but that table shape drifted from WebSettingModel, which reads a
nullable description column. Existing local DBs can be at Alembic head while
still missing this column, causing every pipeline phase to fail during
WebConfigManager initialization.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "k7f8g9h0i1j2"
down_revision: Union[str, Sequence[str], None] = "j6e7f8g9h0i1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE web_settings
        ADD COLUMN IF NOT EXISTS description VARCHAR;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE web_settings
        DROP COLUMN IF EXISTS description;
        """
    )
