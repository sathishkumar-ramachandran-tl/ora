"""add milestone sprint task_dependency agent_tool_call planning_session, promote chat models

Revision ID: 7b1375f2a1b6
Revises: add_new_columns_001
Create Date: 2026-08-02 12:22:23.121974

NOTE: autogenerate only detected the tasks.* column/FK additions below, because
Flask-Migrate boots the app via create_app(), which auto-runs db.create_all() and
silently created the new tables before the diff ran. The CREATE TABLE statements
for milestones/sprints/task_dependencies/agent_tool_calls/planning_sessions were
added by hand to match app/models.py exactly (chat_sessions/chat_messages already
existed pre-migration as inline models in app/api/chat.py, so they're unaffected).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '7b1375f2a1b6'
down_revision = 'add_new_columns_001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'milestones',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('due_date', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('order', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'sprints',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('start_date', sa.DateTime(), nullable=True),
        sa.Column('end_date', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'task_dependencies',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('task_id', sa.String(), nullable=False),
        sa.Column('depends_on_task_id', sa.String(), nullable=False),
        sa.Column('type', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id']),
        sa.ForeignKeyConstraint(['depends_on_task_id'], ['tasks.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('task_id', 'depends_on_task_id', 'type', name='uq_task_dependency'),
    )

    op.create_table(
        'agent_tool_calls',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=True),
        sa.Column('tool_name', sa.String(), nullable=False),
        sa.Column('tool_args', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('tool_result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('workspace_id', sa.String(), nullable=True),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'planning_sessions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('project_id', sa.String(), nullable=True),
        sa.Column('goal_text', sa.Text(), nullable=True),
        sa.Column('phase', sa.String(), nullable=True),
        sa.Column('plan_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('milestone_id', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('sprint_id', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('parent_task_id', sa.String(), nullable=True))
        batch_op.create_foreign_key('fk_tasks_milestone_id', 'milestones', ['milestone_id'], ['id'])
        batch_op.create_foreign_key('fk_tasks_sprint_id', 'sprints', ['sprint_id'], ['id'])
        batch_op.create_foreign_key('fk_tasks_parent_task_id', 'tasks', ['parent_task_id'], ['id'])


def downgrade():
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.drop_constraint('fk_tasks_parent_task_id', type_='foreignkey')
        batch_op.drop_constraint('fk_tasks_sprint_id', type_='foreignkey')
        batch_op.drop_constraint('fk_tasks_milestone_id', type_='foreignkey')
        batch_op.drop_column('parent_task_id')
        batch_op.drop_column('sprint_id')
        batch_op.drop_column('milestone_id')

    op.drop_table('planning_sessions')
    op.drop_table('agent_tool_calls')
    op.drop_table('task_dependencies')
    op.drop_table('sprints')
    op.drop_table('milestones')
