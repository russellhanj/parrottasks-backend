"""drop r2_object_key column from recordings

Revision ID: 151031f7e1e0
Revises: 99544db09c9c
Create Date: 2025-11-01 11:18:54.812518

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '151031f7e1e0'
down_revision: Union[str, Sequence[str], None] = '99544db09c9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # drop only if the column exists (safe for both local + prod)
    conn = op.get_bind()
    has_column = conn.execute(sa.text("""
        SELECT 1
        FROM information_schema.columns
        WHERE table_name='recordings' AND column_name='r2_object_key'
    """)).fetchone()

    if has_column:
        with op.batch_alter_table("recordings") as batch_op:
            batch_op.drop_column("r2_object_key")


def downgrade():
    # add it back if needed
    with op.batch_alter_table("recordings") as batch_op:
        batch_op.add_column(sa.Column("r2_object_key", sa.Text()))
