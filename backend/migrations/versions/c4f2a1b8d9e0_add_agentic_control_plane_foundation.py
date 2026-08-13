"""add agentic control plane foundation

Revision ID: c4f2a1b8d9e0
Revises: 49c02f01de53
Create Date: 2026-08-13 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'c4f2a1b8d9e0'
down_revision = '49c02f01de53'
branch_labels = None
depends_on = None


def _column_exists(table, column):
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name=:t AND column_name=:c"
    ), {"t": table, "c": column})
    return result.fetchone() is not None


def _table_exists(table):
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT table_name FROM information_schema.tables WHERE table_name=:t"
    ), {"t": table})
    return result.fetchone() is not None


def _add_col_if_missing(table, column, column_type, **kwargs):
    if not _column_exists(table, column):
        op.add_column(table, sa.Column(column, column_type, **kwargs))


def upgrade():
    if not _table_exists('agent_runs'):
        op.create_table(
            'agent_runs',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('request_id', sa.String(), nullable=True),
            sa.Column('session_id', sa.String(), nullable=True),
            sa.Column('workspace_id', sa.String(), nullable=True),
            sa.Column('user_id', sa.String(), nullable=True),
            sa.Column('status', sa.String(), nullable=True),
            sa.Column('started_at', sa.DateTime(), nullable=True),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.Column('error_class', sa.String(), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
        )

    if not _table_exists('agent_actions'):
        op.create_table(
            'agent_actions',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('run_id', sa.String(), nullable=False),
            sa.Column('parent_action_id', sa.String(), nullable=True),
            sa.Column('action_type', sa.String(), nullable=False),
            sa.Column('resource_type', sa.String(), nullable=True),
            sa.Column('resource_id', sa.String(), nullable=True),
            sa.Column('status', sa.String(), nullable=True),
            sa.Column('risk_level', sa.String(), nullable=True),
            sa.Column('confirmation_required', sa.Boolean(), nullable=True),
            sa.Column('idempotency_key', sa.String(), nullable=True),
            sa.Column('request_fingerprint', sa.String(), nullable=True),
            sa.Column('proposed_args', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('before_state', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('after_state', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['run_id'], ['agent_runs.id']),
            sa.ForeignKeyConstraint(['parent_action_id'], ['agent_actions.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_agent_actions_idempotency_key', 'agent_actions', ['idempotency_key'])
        op.create_index('ix_agent_actions_request_fingerprint', 'agent_actions', ['request_fingerprint'])

    for column, typ in [
        ('run_id', sa.String()),
        ('action_id', sa.String()),
        ('execution_status', sa.String()),
        ('verification_status', sa.String()),
        ('attempt_number', sa.Integer()),
        ('error_class', sa.String()),
        ('error_message', sa.Text()),
        ('external_provider', sa.String()),
        ('external_resource_id', sa.String()),
        ('started_at', sa.DateTime()),
        ('completed_at', sa.DateTime()),
        ('verified_at', sa.DateTime()),
    ]:
        _add_col_if_missing('agent_tool_calls', column, typ, nullable=True)

    for column, typ in [
        ('scope_level', sa.String()),
        ('scope_project_id', sa.String()),
        ('scope_task_id', sa.String()),
    ]:
        _add_col_if_missing('chat_sessions', column, typ, nullable=True)


def downgrade():
    for column in ['scope_task_id', 'scope_project_id', 'scope_level']:
        if _column_exists('chat_sessions', column):
            op.drop_column('chat_sessions', column)

    for column in [
        'verified_at', 'completed_at', 'started_at', 'external_resource_id',
        'external_provider', 'error_message', 'error_class', 'attempt_number',
        'verification_status', 'execution_status', 'action_id', 'run_id',
    ]:
        if _column_exists('agent_tool_calls', column):
            op.drop_column('agent_tool_calls', column)

    if _table_exists('agent_actions'):
        op.drop_table('agent_actions')
    if _table_exists('agent_runs'):
        op.drop_table('agent_runs')

