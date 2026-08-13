"""add scheduling calendar foundation

Revision ID: g4b5c6d7e8f9
Revises: f3a4c5d6e7b9
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'g4b5c6d7e8f9'
down_revision = 'f3a4c5d6e7b9'
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return column_name in {col['name'] for col in insp.get_columns(table_name)}


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def upgrade():
    with op.batch_alter_table('calendar_events', schema=None) as batch_op:
        if not _has_column('calendar_events', 'is_flexible'):
            batch_op.add_column(sa.Column('is_flexible', sa.Boolean(), nullable=True, server_default=sa.true()))
        if not _has_column('calendar_events', 'locked'):
            batch_op.add_column(sa.Column('locked', sa.Boolean(), nullable=True, server_default=sa.false()))
        if not _has_column('calendar_events', 'session_status'):
            batch_op.add_column(sa.Column('session_status', sa.String(), nullable=True, server_default='SCHEDULED'))
        if not _has_column('calendar_events', 'completed_at'):
            batch_op.add_column(sa.Column('completed_at', sa.DateTime(), nullable=True))

    with op.batch_alter_table('agent_actions', schema=None) as batch_op:
        if not _has_column('agent_actions', 'reversible'):
            batch_op.add_column(sa.Column('reversible', sa.Boolean(), nullable=True, server_default=sa.false()))
        if not _has_column('agent_actions', 'compensation_action_type'):
            batch_op.add_column(sa.Column('compensation_action_type', sa.String(), nullable=True))
        if not _has_column('agent_actions', 'original_action_id'):
            batch_op.add_column(sa.Column('original_action_id', sa.String(), nullable=True))
            batch_op.create_foreign_key('fk_agent_actions_original_action_id', 'agent_actions', ['original_action_id'], ['id'])
        if not _has_column('agent_actions', 'undo_action_id'):
            batch_op.add_column(sa.Column('undo_action_id', sa.String(), nullable=True))
            batch_op.create_foreign_key('fk_agent_actions_undo_action_id', 'agent_actions', ['undo_action_id'], ['id'])
        if not _has_column('agent_actions', 'undo_status'):
            batch_op.add_column(sa.Column('undo_status', sa.String(), nullable=True))

    if not _table_exists('schedule_proposals'):
        op.create_table(
            'schedule_proposals',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('run_id', sa.String(), nullable=True),
            sa.Column('workspace_id', sa.String(), nullable=False),
            sa.Column('user_id', sa.String(), nullable=True),
            sa.Column('status', sa.String(), nullable=True),
            sa.Column('version', sa.Integer(), nullable=True),
            sa.Column('window_start', sa.DateTime(), nullable=False),
            sa.Column('window_end', sa.DateTime(), nullable=False),
            sa.Column('timezone', sa.String(), nullable=True),
            sa.Column('constraints', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('sessions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('compiled_actions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('application_result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('applied_action_id', sa.String(), nullable=True),
            sa.Column('supersedes_id', sa.String(), nullable=True),
            sa.Column('revision_reason', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('applied_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['applied_action_id'], ['agent_actions.id']),
            sa.ForeignKeyConstraint(['run_id'], ['agent_runs.id']),
            sa.ForeignKeyConstraint(['supersedes_id'], ['schedule_proposals.id']),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
            sa.PrimaryKeyConstraint('id'),
        )


def downgrade():
    if _table_exists('schedule_proposals'):
        op.drop_table('schedule_proposals')

    with op.batch_alter_table('agent_actions', schema=None) as batch_op:
        for fk_name in ('fk_agent_actions_undo_action_id', 'fk_agent_actions_original_action_id'):
            try:
                batch_op.drop_constraint(fk_name, type_='foreignkey')
            except Exception:
                pass
        for column in ('undo_status', 'undo_action_id', 'original_action_id', 'compensation_action_type', 'reversible'):
            if _has_column('agent_actions', column):
                batch_op.drop_column(column)

    with op.batch_alter_table('calendar_events', schema=None) as batch_op:
        for column in ('completed_at', 'session_status', 'locked', 'is_flexible'):
            if _has_column('calendar_events', column):
                batch_op.drop_column(column)
