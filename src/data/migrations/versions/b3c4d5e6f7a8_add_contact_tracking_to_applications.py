"""add_contact_tracking_to_applications

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-05-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('applications', sa.Column('last_contact_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('applications', sa.Column('next_follow_up_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('applications', 'next_follow_up_at')
    op.drop_column('applications', 'last_contact_at')
