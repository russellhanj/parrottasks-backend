"""create recordings table

Revision ID: 94d3bc441d85
Revises: c0a8210f0235
Create Date: 2025-10-25 10:08:33.198448

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '94d3bc441d85'
down_revision: Union[str, Sequence[str], None] = 'c0a8210f0235'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Add new columns as nullable first
    op.add_column('recordings', sa.Column('mime_type', sa.String(length=128), nullable=True))
    op.add_column('recordings', sa.Column('file_size', sa.Integer(), nullable=True))
    op.add_column('recordings', sa.Column('sha256', sa.String(length=64), nullable=True))
    op.add_column('recordings', sa.Column('r2_key', sa.String(length=512), nullable=True))

    # 2) Backfill existing rows with safe defaults
    op.execute("""
        UPDATE recordings
        SET
          mime_type = COALESCE(mime_type, 'application/octet-stream'),
          file_size = COALESCE(file_size, 0),
          sha256    = COALESCE(sha256, 'legacy'),
          r2_key    = COALESCE(r2_key, 'legacy/' || id)
    """)

    # 3) Enforce NOT NULL
    op.alter_column('recordings', 'mime_type', existing_type=sa.String(length=128), nullable=False)
    op.alter_column('recordings', 'file_size', existing_type=sa.Integer(), nullable=False)
    op.alter_column('recordings', 'sha256',    existing_type=sa.String(length=64), nullable=False)
    op.alter_column('recordings', 'r2_key',    existing_type=sa.String(length=512), nullable=False)

    # 4) Indexes / constraints (match your model)
    op.create_index('ix_recordings_sha256', 'recordings', ['sha256'])
    op.create_index('ix_recordings_status', 'recordings', ['status'])
    op.create_unique_constraint('uq_recordings_r2_key', 'recordings', ['r2_key'])

def downgrade() -> None:
    op.drop_constraint('uq_recordings_r2_key', 'recordings', type_='unique')
    op.drop_index('ix_recordings_status', table_name='recordings')
    op.drop_index('ix_recordings_sha256', table_name='recordings')
    op.drop_column('recordings', 'r2_key')
    op.drop_column('recordings', 'sha256')
    op.drop_column('recordings', 'file_size')
    op.drop_column('recordings', 'mime_type')
