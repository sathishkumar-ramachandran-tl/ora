"""add knowledge coverage models

Revision ID: e91a32c4d7b8
Revises: d2b7f90a4c13
Create Date: 2026-08-13 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'e91a32c4d7b8'
down_revision = 'd2b7f90a4c13'
branch_labels = None
depends_on = None


def _table_exists(table):
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT table_name FROM information_schema.tables WHERE table_name=:t"
    ), {"t": table})
    return result.fetchone() is not None


def upgrade():
    if not _table_exists('concepts'):
        op.create_table(
            'concepts',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('workspace_id', sa.String(), nullable=False),
            sa.Column('concept_key', sa.String(), nullable=False),
            sa.Column('canonical_name', sa.String(), nullable=False),
            sa.Column('domain', sa.String(), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('workspace_id', 'concept_key', name='uq_concepts_workspace_key'),
        )

    if not _table_exists('concept_aliases'):
        op.create_table(
            'concept_aliases',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('concept_id', sa.String(), nullable=False),
            sa.Column('alias', sa.String(), nullable=False),
            sa.Column('normalized_alias', sa.String(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['concept_id'], ['concepts.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('concept_id', 'normalized_alias', name='uq_concept_alias_normalized'),
        )

    if not _table_exists('concept_relationships'):
        op.create_table(
            'concept_relationships',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('workspace_id', sa.String(), nullable=False),
            sa.Column('source_concept_id', sa.String(), nullable=False),
            sa.Column('target_concept_id', sa.String(), nullable=False),
            sa.Column('relationship_type', sa.String(), nullable=False),
            sa.Column('evidence', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
            sa.ForeignKeyConstraint(['source_concept_id'], ['concepts.id']),
            sa.ForeignKeyConstraint(['target_concept_id'], ['concepts.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint(
                'source_concept_id', 'target_concept_id', 'relationship_type',
                name='uq_concept_relationship',
            ),
        )

    if not _table_exists('coverage_records'):
        op.create_table(
            'coverage_records',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('workspace_id', sa.String(), nullable=False),
            sa.Column('project_id', sa.String(), nullable=True),
            sa.Column('plan_proposal_id', sa.String(), nullable=True),
            sa.Column('concept_id', sa.String(), nullable=False),
            sa.Column('concept_key', sa.String(), nullable=False),
            sa.Column('concept_name', sa.String(), nullable=False),
            sa.Column('domain', sa.String(), nullable=True),
            sa.Column('coverage_type', sa.String(), nullable=False),
            sa.Column('depth', sa.String(), nullable=False),
            sa.Column('status', sa.String(), nullable=True),
            sa.Column('source_type', sa.String(), nullable=False),
            sa.Column('source_id', sa.String(), nullable=True),
            sa.Column('evidence', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
            sa.ForeignKeyConstraint(['plan_proposal_id'], ['plan_proposals.id']),
            sa.ForeignKeyConstraint(['concept_id'], ['concepts.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint(
                'workspace_id', 'plan_proposal_id', 'concept_key', 'coverage_type',
                'depth', 'source_type', 'source_id',
                name='uq_coverage_record_identity',
            ),
        )
        op.create_index('ix_coverage_records_workspace_domain', 'coverage_records', ['workspace_id', 'domain'])
        op.create_index('ix_coverage_records_project_id', 'coverage_records', ['project_id'])


def downgrade():
    if _table_exists('coverage_records'):
        op.drop_index('ix_coverage_records_project_id', table_name='coverage_records')
        op.drop_index('ix_coverage_records_workspace_domain', table_name='coverage_records')
        op.drop_table('coverage_records')
    if _table_exists('concept_relationships'):
        op.drop_table('concept_relationships')
    if _table_exists('concept_aliases'):
        op.drop_table('concept_aliases')
    if _table_exists('concepts'):
        op.drop_table('concepts')
