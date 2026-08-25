"""rename_oss_fields_to_local_storage

Revision ID: 35b02da1a336
Revises: 5a762d37fb2d
Create Date: 2026-05-07 17:29:10.081821

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '35b02da1a336'
down_revision: Union[str, Sequence[str], None] = '5a762d37fb2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: 将 OSS 遗留字段名改为语义化的本地存储命名。"""
    op.alter_column('tasks', 'video_oss_key', new_column_name='source_path')
    op.alter_column('clips', 'oss_key', new_column_name='file_key')


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('tasks', 'source_path', new_column_name='video_oss_key')
    op.alter_column('clips', 'file_key', new_column_name='oss_key')
