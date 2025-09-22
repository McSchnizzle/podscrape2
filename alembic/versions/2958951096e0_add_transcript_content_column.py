"""add_transcript_content_column

Revision ID: 2958951096e0
Revises: 5f1c9f0c9e4b
Create Date: 2025-09-21 21:24:34.499463

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2958951096e0'
down_revision: Union[str, Sequence[str], None] = '5f1c9f0c9e4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add transcript_content TEXT column to episodes table."""
    # Add transcript_content column to episodes table
    op.add_column('episodes', sa.Column('transcript_content', sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove transcript_content column from episodes table."""
    # Remove transcript_content column from episodes table
    op.drop_column('episodes', 'transcript_content')
