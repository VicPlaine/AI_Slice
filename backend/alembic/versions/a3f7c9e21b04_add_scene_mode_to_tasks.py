"""add_scene_mode_to_tasks

Revision ID: a3f7c9e21b04
Revises: 89b5d32c1dfb
Create Date: 2026-04-22 15:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f7c9e21b04'
down_revision: Union[str, Sequence[str], None] = '89b5d32c1dfb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tasks', sa.Column('scene_mode', sa.String(30), server_default='livestream', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('tasks', 'scene_mode')
