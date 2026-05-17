"""add_saved_searches

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-05-15 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'saved_searches',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('keywords', sa.String(256), nullable=False),
        sa.Column('location', sa.String(256), nullable=False),
        sa.Column('sources', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('min_match_score', sa.Float(), nullable=False, server_default='0.6'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('run_every_hours', sa.Integer(), nullable=False, server_default='24'),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('saved_searches')
