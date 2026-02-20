"""Add saturation_score column to story_arcs for coverage tracking

Revision ID: g3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-02-20 09:40:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g3b4c5d6e7f8'
down_revision = 'f2a3b4c5d6e7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add saturation_score: 0.0 (never covered) to 1.0 (fully saturated)
    op.add_column('story_arcs', sa.Column(
        'saturation_score', sa.Float(), nullable=False, server_default='0.0'
    ))

    # Initialize saturation from existing coverage data
    # Arcs covered once get 0.3, covered in multiple digests get higher scores
    op.execute('''
        UPDATE story_arcs sa SET saturation_score = LEAST(1.0,
            (SELECT COUNT(*) FROM story_arc_coverage sac
             WHERE sac.story_arc_id = sa.id) * 0.3
        )
    ''')


def downgrade() -> None:
    op.drop_column('story_arcs', 'saturation_score')
