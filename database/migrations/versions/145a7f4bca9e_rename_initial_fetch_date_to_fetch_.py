"""rename_initial_fetch_date_to_fetch_cutoff

Revision ID: 145a7f4bca9e
Revises: 509f103fb205
Create Date: 2024-04-26 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '145a7f4bca9e'
down_revision = '509f103fb205'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE settings SET key = 'fetch_cutoff', type = 'datetime' WHERE key = 'sources.habr.initial_fetch_date'")


def downgrade():
    op.execute("UPDATE settings SET key = 'sources.habr.initial_fetch_date', type = 'string' WHERE key = 'fetch_cutoff'")