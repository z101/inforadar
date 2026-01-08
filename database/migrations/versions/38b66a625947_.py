"""empty message

Revision ID: 38b66a625947
Revises: 145a7f4bca9e, b595316ec9cb
Create Date: 2026-01-07 15:04:36.486396

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '38b66a625947'
down_revision: Union[str, Sequence[str], None] = ('145a7f4bca9e', 'b595316ec9cb')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
