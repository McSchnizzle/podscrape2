"""change_workflow_run_id_to_bigint

Revision ID: 199afb551ab0
Revises: c4d5e6f7a8b9
Create Date: 2025-12-15 09:03:08.573829

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '199afb551ab0'
down_revision: Union[str, Sequence[str], None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change workflow_run_id from INTEGER to BIGINT for large GitHub run IDs."""
    op.alter_column(
        'workflow_errors',
        'workflow_run_id',
        type_=sa.BigInteger(),
        existing_type=sa.Integer(),
        existing_nullable=True
    )


def downgrade() -> None:
    """Revert workflow_run_id to INTEGER."""
    op.alter_column(
        'workflow_errors',
        'workflow_run_id',
        type_=sa.Integer(),
        existing_type=sa.BigInteger(),
        existing_nullable=True
    )
