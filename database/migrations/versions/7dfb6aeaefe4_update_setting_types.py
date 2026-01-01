"""Update setting types

Revision ID: 7dfb6aeaefe4
Revises: dc80ed259b9b
Create Date: 2026-01-01 15:24:04.088529

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7dfb6aeaefe4'
down_revision: Union[str, Sequence[str], None] = 'dc80ed259b9b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
