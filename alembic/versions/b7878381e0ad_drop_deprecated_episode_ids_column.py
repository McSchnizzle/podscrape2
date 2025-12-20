"""drop_deprecated_episode_ids_column

Revision ID: b7878381e0ad
Revises: 3cb98f7a9984
Create Date: 2025-12-20 10:31:31.316392

Issue #29: Final cleanup from Issue #10 (digest-episode linkage unification).
The digest_episode_links join table is now the single source of truth.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b7878381e0ad'
down_revision: Union[str, Sequence[str], None] = '3cb98f7a9984'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop deprecated episode_ids JSON column from digests table.

    Issue #29: This column was deprecated by Issue #10 which created the
    digest_episode_links join table as the single source of truth.
    """
    op.drop_column('digests', 'episode_ids')


def downgrade() -> None:
    """Re-add episode_ids column if rollback needed."""
    op.add_column('digests', sa.Column('episode_ids', postgresql.JSONB(), nullable=True))
