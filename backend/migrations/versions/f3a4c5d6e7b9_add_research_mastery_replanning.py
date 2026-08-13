"""add research mastery replanning

Revision ID: f3a4c5d6e7b9
Revises: e91a32c4d7b8
Create Date: 2026-08-13 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'f3a4c5d6e7b9'
down_revision = 'e91a32c4d7b8'
branch_labels = None
depends_on = None


def _table_exists(table):
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT table_name FROM information_schema.tables WHERE table_name=:t"
    ), {"t": table})
    return result.fetchone() is not None


def upgrade():
    if not _table_exists('research_evidence'):
        op.create_table(
            'research_evidence',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('workspace_id', sa.String(), nullable=False),
            sa.Column('run_id', sa.String(), nullable=True),
            sa.Column('domain', sa.String(), nullable=False),
            sa.Column('topic', sa.String(), nullable=True),
            sa.Column('source_type', sa.String(), nullable=False),
            sa.Column('title', sa.String(), nullable=False),
            sa.Column('source_url', sa.String(), nullable=True),
            sa.Column('authority_level', sa.String(), nullable=False),
            sa.Column('claims', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('topics', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('relevance', sa.String(), nullable=True),
            sa.Column('content_hash', sa.String(), nullable=True),
            sa.Column('retrieved_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
            sa.ForeignKeyConstraint(['run_id'], ['agent_runs.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_research_evidence_workspace_domain', 'research_evidence', ['workspace_id', 'domain'])
        op.create_index('ix_research_evidence_content_hash', 'research_evidence', ['content_hash'])

    if not _table_exists('competency_evidence'):
        op.create_table(
            'competency_evidence',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('workspace_id', sa.String(), nullable=False),
            sa.Column('user_id', sa.String(), nullable=True),
            sa.Column('concept_id', sa.String(), nullable=True),
            sa.Column('evidence_type', sa.String(), nullable=False),
            sa.Column('evidence_ref', sa.String(), nullable=True),
            sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('strength', sa.String(), nullable=True),
            sa.Column('assessed_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.ForeignKeyConstraint(['concept_id'], ['concepts.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_competency_evidence_workspace_user', 'competency_evidence', ['workspace_id', 'user_id'])

    if not _table_exists('mastery_records'):
        op.create_table(
            'mastery_records',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('workspace_id', sa.String(), nullable=False),
            sa.Column('user_id', sa.String(), nullable=True),
            sa.Column('concept_id', sa.String(), nullable=False),
            sa.Column('concept_key', sa.String(), nullable=False),
            sa.Column('status', sa.String(), nullable=True),
            sa.Column('evidence_type', sa.String(), nullable=True),
            sa.Column('evidence_id', sa.String(), nullable=True),
            sa.Column('assessed_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.ForeignKeyConstraint(['concept_id'], ['concepts.id']),
            sa.ForeignKeyConstraint(['evidence_id'], ['competency_evidence.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('workspace_id', 'user_id', 'concept_id', name='uq_mastery_user_concept'),
        )
        op.create_index('ix_mastery_records_workspace_key', 'mastery_records', ['workspace_id', 'concept_key'])

    if not _table_exists('plan_revision_proposals'):
        op.create_table(
            'plan_revision_proposals',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('workspace_id', sa.String(), nullable=False),
            sa.Column('base_plan_id', sa.String(), nullable=False),
            sa.Column('base_version', sa.Integer(), nullable=False),
            sa.Column('trigger', sa.String(), nullable=False),
            sa.Column('hard_constraints', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('soft_preferences', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('operations', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('rationale', sa.Text(), nullable=True),
            sa.Column('status', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('applied_plan_id', sa.String(), nullable=True),
            sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
            sa.ForeignKeyConstraint(['base_plan_id'], ['plan_proposals.id']),
            sa.ForeignKeyConstraint(['applied_plan_id'], ['plan_proposals.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_plan_revision_base_plan', 'plan_revision_proposals', ['base_plan_id'])


def downgrade():
    if _table_exists('plan_revision_proposals'):
        op.drop_index('ix_plan_revision_base_plan', table_name='plan_revision_proposals')
        op.drop_table('plan_revision_proposals')
    if _table_exists('mastery_records'):
        op.drop_index('ix_mastery_records_workspace_key', table_name='mastery_records')
        op.drop_table('mastery_records')
    if _table_exists('competency_evidence'):
        op.drop_index('ix_competency_evidence_workspace_user', table_name='competency_evidence')
        op.drop_table('competency_evidence')
    if _table_exists('research_evidence'):
        op.drop_index('ix_research_evidence_content_hash', table_name='research_evidence')
        op.drop_index('ix_research_evidence_workspace_domain', table_name='research_evidence')
        op.drop_table('research_evidence')
