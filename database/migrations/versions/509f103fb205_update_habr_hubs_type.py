"""update_habr_hubs_type

Revision ID: 509f103fb205
Revises: 7dfb6aeaefe4
Create Date: 2026-01-02 00:30:10.983599

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '509f103fb205'
down_revision: Union[str, Sequence[str], None] = '7dfb6aeaefe4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("UPDATE settings SET type = 'habr_hubs' WHERE key = 'sources.habr.hubs'")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE settings SET type = 'json' WHERE key = 'sources.habr.hubs'")
