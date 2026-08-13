"""add plan proposals

Revision ID: d2b7f90a4c13
Revises: c4f2a1b8d9e0
Create Date: 2026-08-13 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'd2b7f90a4c13'
down_revision = 'c4f2a1b8d9e0'
branch_labels = None
depends_on = None


def _table_exists(table):
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT table_name FROM information_schema.tables WHERE table_name=:t"
    ), {"t": table})
    return result.fetchone() is not None


def upgrade():
    if not _table_exists('plan_proposals'):
        op.create_table(
            'plan_proposals',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('run_id', sa.String(), nullable=True),
            sa.Column('workspace_id', sa.String(), nullable=False),
            sa.Column('user_id', sa.String(), nullable=True),
            sa.Column('scope_level', sa.String(), nullable=True),
            sa.Column('scope_project_id', sa.String(), nullable=True),
            sa.Column('scope_task_id', sa.String(), nullable=True),
            sa.Column('title', sa.String(), nullable=False),
            sa.Column('goal', sa.Text(), nullable=True),
            sa.Column('status', sa.String(), nullable=True),
            sa.Column('version', sa.Integer(), nullable=True),
            sa.Column('quality_status', sa.String(), nullable=True),
            sa.Column('supersedes_id', sa.String(), nullable=True),
            sa.Column('revision_reason', sa.Text(), nullable=True),
            sa.Column('content', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('planning_context', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('quality_report', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('duplication_report', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('compiled_actions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('application_result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('applied_action_id', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('applied_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['run_id'], ['agent_runs.id']),
            sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.ForeignKeyConstraint(['scope_project_id'], ['projects.id']),
            sa.ForeignKeyConstraint(['scope_task_id'], ['tasks.id']),
            sa.ForeignKeyConstraint(['supersedes_id'], ['plan_proposals.id']),
            sa.ForeignKeyConstraint(['applied_action_id'], ['agent_actions.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_plan_proposals_workspace_id', 'plan_proposals', ['workspace_id'])
        op.create_index('ix_plan_proposals_run_id', 'plan_proposals', ['run_id'])


def downgrade():
    if _table_exists('plan_proposals'):
        op.drop_index('ix_plan_proposals_run_id', table_name='plan_proposals')
        op.drop_index('ix_plan_proposals_workspace_id', table_name='plan_proposals')
        op.drop_table('plan_proposals')
