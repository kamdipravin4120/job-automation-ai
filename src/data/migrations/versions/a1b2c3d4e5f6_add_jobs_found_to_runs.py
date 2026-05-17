"""add_jobs_found_to_runs

Revision ID: a1b2c3d4e5f6
Revises: 7cb2e2ceea6a
Create Date: 2026-05-07 10:21:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '7cb2e2ceea6a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('runs', sa.Column('jobs_found', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('runs', 'jobs_found')
