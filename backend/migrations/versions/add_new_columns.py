"""add new columns: country/purpose to users, jira fields to tasks, analytics to activity_logs

Revision ID: add_new_columns_001
Revises:
Create Date: 2026-05-17

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'add_new_columns_001'
down_revision = None
branch_labels = None
depends_on = None


def column_exists(table, column):
    from alembic import op as _op
    from sqlalchemy import inspect, text
    conn = op.get_bind()
    result = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name=:t AND column_name=:c"
    ), {"t": table, "c": column})
    return result.fetchone() is not None


def upgrade():
    conn = op.get_bind()
    from sqlalchemy import text

    def add_col_if_missing(table, col, col_type):
        result = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name=:t AND column_name=:c"
        ), {"t": table, "c": col})
        if not result.fetchone():
            op.add_column(table, sa.Column(col, col_type, nullable=True))

    # Users: country, purpose
    add_col_if_missing('users', 'country', sa.String())
    add_col_if_missing('users', 'purpose', sa.String())

    # Tasks: labels (JSONB), issue_type, due_date, assignee_id
    add_col_if_missing('tasks', 'labels', postgresql.JSONB(astext_type=sa.Text()))
    add_col_if_missing('tasks', 'issue_type', sa.String())
    add_col_if_missing('tasks', 'due_date', sa.DateTime())
    add_col_if_missing('tasks', 'assignee_id', sa.String())

    # ActivityLog: user_id, workspace_id, session_id, platform
    add_col_if_missing('activity_logs', 'user_id', sa.String())
    add_col_if_missing('activity_logs', 'workspace_id', sa.String())
    add_col_if_missing('activity_logs', 'session_id', sa.String())
    add_col_if_missing('activity_logs', 'platform', sa.String())


def downgrade():
    pass
