"""replace interview scene mode with podcast

Revision ID: 7c9e1a2b3d4f
Revises: 35b02da1a336
Create Date: 2026-08-25 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "7c9e1a2b3d4f"
down_revision: Union[str, Sequence[str], None] = "35b02da1a336"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Migrate existing task labels to the new podcast mode."""
    op.execute("UPDATE tasks SET scene_mode = 'podcast' WHERE scene_mode = 'interview'")


def downgrade() -> None:
    """Restore the previous mode identifier."""
    op.execute("UPDATE tasks SET scene_mode = 'interview' WHERE scene_mode = 'podcast'")
