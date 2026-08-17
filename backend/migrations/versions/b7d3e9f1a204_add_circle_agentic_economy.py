"""add circle agentic economy foundation

Revision ID: b7d3e9f1a204
Revises: a6c8f2d4e901
Create Date: 2026-08-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b7d3e9f1a204'
down_revision = 'a6c8f2d4e901'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'agent_wallets',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('circle_wallet_id', sa.String(), nullable=True),
        sa.Column('circle_wallet_set_id', sa.String(), nullable=True),
        sa.Column('address', sa.String(), nullable=True),
        sa.Column('blockchain', sa.String(), nullable=False),
        sa.Column('custody_type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('is_simulated', sa.Boolean(), nullable=True),
        sa.Column('simulated_balance_usdc', sa.Numeric(18, 6), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id', name='uq_agent_wallets_workspace_id'),
    )

    op.create_table(
        'economic_policies',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('per_transaction_limit_usdc', sa.Numeric(18, 6), nullable=True),
        sa.Column('daily_limit_usdc', sa.Numeric(18, 6), nullable=True),
        sa.Column('monthly_limit_usdc', sa.Numeric(18, 6), nullable=True),
        sa.Column('auto_approve_threshold_usdc', sa.Numeric(18, 6), nullable=True),
        sa.Column('allowed_capability_categories', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('allowed_providers', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('blocked_providers', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('require_confirmation_above_threshold', sa.Boolean(), nullable=True),
        sa.Column('emergency_stop', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id', name='uq_economic_policies_workspace_id'),
    )

    op.create_table(
        'capability_providers',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('capability', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('endpoint', sa.String(), nullable=False),
        sa.Column('price_usdc', sa.Numeric(18, 6), nullable=False),
        sa.Column('currency', sa.String(), nullable=True),
        sa.Column('payment_mechanism', sa.String(), nullable=True),
        sa.Column('wallet_address', sa.String(), nullable=True),
        sa.Column('chain', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('estimated_latency_ms', sa.Integer(), nullable=True),
        sa.Column('total_calls', sa.Integer(), nullable=True),
        sa.Column('total_successes', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_capability_providers_capability', 'capability_providers', ['capability'])

    op.create_table(
        'economic_actions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('run_id', sa.String(), nullable=True),
        sa.Column('action_id', sa.String(), nullable=True),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('capability', sa.String(), nullable=False),
        sa.Column('task_description', sa.Text(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('provider_id', sa.String(), nullable=True),
        sa.Column('requested_amount_usdc', sa.Numeric(18, 6), nullable=False),
        sa.Column('currency', sa.String(), nullable=True),
        sa.Column('constraints', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('policy_decision', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('service_result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('verification_status', sa.String(), nullable=True),
        sa.Column('verification_notes', sa.Text(), nullable=True),
        sa.Column('quality_score', sa.Float(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['run_id'], ['agent_runs.id']),
        sa.ForeignKeyConstraint(['action_id'], ['agent_actions.id']),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['provider_id'], ['capability_providers.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'payment_transactions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('economic_action_id', sa.String(), nullable=False),
        sa.Column('wallet_id', sa.String(), nullable=False),
        sa.Column('circle_transaction_id', sa.String(), nullable=True),
        sa.Column('transaction_hash', sa.String(), nullable=True),
        sa.Column('from_address', sa.String(), nullable=True),
        sa.Column('to_address', sa.String(), nullable=True),
        sa.Column('chain', sa.String(), nullable=False),
        sa.Column('amount_usdc', sa.Numeric(18, 6), nullable=False),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('explorer_url', sa.String(), nullable=True),
        sa.Column('is_simulated', sa.Boolean(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['economic_action_id'], ['economic_actions.id']),
        sa.ForeignKeyConstraint(['wallet_id'], ['agent_wallets.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'economic_evidence',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('economic_action_id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('user_goal', sa.Text(), nullable=True),
        sa.Column('capability', sa.String(), nullable=False),
        sa.Column('provider_name', sa.String(), nullable=False),
        sa.Column('price_usdc', sa.Numeric(18, 6), nullable=False),
        sa.Column('payment_transaction_id', sa.String(), nullable=True),
        sa.Column('circle_wallet_address', sa.String(), nullable=True),
        sa.Column('circle_transaction_id', sa.String(), nullable=True),
        sa.Column('transaction_hash', sa.String(), nullable=True),
        sa.Column('explorer_url', sa.String(), nullable=True),
        sa.Column('service_result_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('verification_status', sa.String(), nullable=True),
        sa.Column('quality_score', sa.Float(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['economic_action_id'], ['economic_actions.id']),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.ForeignKeyConstraint(['payment_transaction_id'], ['payment_transactions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('economic_action_id', name='uq_economic_evidence_action_id'),
    )


def downgrade():
    op.drop_table('economic_evidence')
    op.drop_table('payment_transactions')
    op.drop_table('economic_actions')
    op.drop_index('ix_capability_providers_capability', table_name='capability_providers')
    op.drop_table('capability_providers')
    op.drop_table('economic_policies')
    op.drop_table('agent_wallets')
