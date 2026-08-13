"""add rate limit counters

Revision ID: a6c8f2d4e901
Revises: g4b5c6d7e8f9
Create Date: 2026-08-14 01:10:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'a6c8f2d4e901'
down_revision = 'g4b5c6d7e8f9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'rate_limit_counters',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('key_hash', sa.String(length=64), nullable=False),
        sa.Column('policy', sa.String(length=32), nullable=False),
        sa.Column('window_start', sa.DateTime(), nullable=False),
        sa.Column('count', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key_hash', 'policy', name='uq_rate_limit_key_policy'),
    )
    op.create_index('ix_rate_limit_policy_window', 'rate_limit_counters', ['policy', 'window_start'])


def downgrade():
    op.drop_index('ix_rate_limit_policy_window', table_name='rate_limit_counters')
    op.drop_table('rate_limit_counters')
