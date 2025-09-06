"""init schema

Revision ID: c0a8210f0235
Revises: f6efcb4d709a
Create Date: 2025-09-06 09:22:08.697009

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c0a8210f0235'
down_revision: Union[str, Sequence[str], None] = 'f6efcb4d709a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
