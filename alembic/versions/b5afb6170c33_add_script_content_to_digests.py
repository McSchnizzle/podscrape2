"""add_script_content_to_digests

Revision ID: b5afb6170c33
Revises: 421544bfb39c
Create Date: 2025-09-28 19:52:38.941811

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5afb6170c33'
down_revision: Union[str, Sequence[str], None] = '421544bfb39c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add script_content TEXT column to digests table."""
    # Add script_content column to digests table
    op.add_column('digests', sa.Column('script_content', sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove script_content column from digests table."""
    # Remove script_content column from digests table
    op.drop_column('digests', 'script_content')
