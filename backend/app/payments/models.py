import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from ..core.extensions import db
from .economic_control import WalletStatus


def generate_uuid():
    return str(uuid.uuid4())


class AgentWallet(db.Model):
    """A Circle-controlled USDC wallet giving a workspace its own economic identity.

    Custody stays with Circle (developer-controlled wallet) — Ora never holds private
    keys. `simulated_balance_usdc` only backs the wallet when Circle isn't configured
    (see circle_client.py); once CIRCLE_API_KEY is set, balance is always read live
    from Circle and this column is unused."""
    __tablename__ = 'agent_wallets'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'), nullable=False, unique=True)

    circle_wallet_id = db.Column(db.String, nullable=True)
    circle_wallet_set_id = db.Column(db.String, nullable=True)
    address = db.Column(db.String, nullable=True)
    blockchain = db.Column(db.String, nullable=False, default='MATIC-AMOY')
    custody_type = db.Column(db.String, nullable=False, default='DEVELOPER')
    status = db.Column(db.String, default=WalletStatus.CREATING.value)

    is_simulated = db.Column(db.Boolean, default=True)
    simulated_balance_usdc = db.Column(db.Numeric(18, 6), default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EconomicPolicy(db.Model):
    """Workspace-level spending policy — the deterministic gate every EconomicAction
    must pass through before a payment can execute. One row per workspace, created
    lazily with conservative defaults on first use (see policy.get_or_create_policy)."""
    __tablename__ = 'economic_policies'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'), nullable=False, unique=True)

    per_transaction_limit_usdc = db.Column(db.Numeric(18, 6), default=1.0)
    daily_limit_usdc = db.Column(db.Numeric(18, 6), default=5.0)
    monthly_limit_usdc = db.Column(db.Numeric(18, 6), nullable=True)  # null = no monthly cap
    auto_approve_threshold_usdc = db.Column(db.Numeric(18, 6), default=0.10)

    # Empty/null list = no restriction (all capabilities / all providers allowed).
    allowed_capability_categories = db.Column(JSONB, default=list)
    allowed_providers = db.Column(JSONB, default=list)
    blocked_providers = db.Column(JSONB, default=list)

    require_confirmation_above_threshold = db.Column(db.Boolean, default=True)
    emergency_stop = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CapabilityProvider(db.Model):
    """A registered external capability/service an Ora agent can autonomously buy.
    Deliberately a DB-backed registry (not a hardcoded provider) so the marketplace can
    grow to many providers per capability without a code change — see discovery.py."""
    __tablename__ = 'capability_providers'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)

    capability = db.Column(db.String, nullable=False, index=True)  # e.g. "competitor_research"
    name = db.Column(db.String, nullable=False)
    provider = db.Column(db.String, nullable=False)  # organization/brand behind the capability
    description = db.Column(db.Text)
    endpoint = db.Column(db.String, nullable=False)  # service identifier: https:// URL or "sim://..."

    price_usdc = db.Column(db.Numeric(18, 6), nullable=False)
    currency = db.Column(db.String, default='USDC')
    payment_mechanism = db.Column(db.String, default='circle_usdc_transfer')
    wallet_address = db.Column(db.String, nullable=True)  # destination address for payment
    chain = db.Column(db.String, nullable=False, default='MATIC-AMOY')

    is_active = db.Column(db.Boolean, default=True)
    estimated_latency_ms = db.Column(db.Integer, default=3000)

    total_calls = db.Column(db.Integer, default=0)
    total_successes = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def success_rate(self) -> float:
        if not self.total_calls:
            return 1.0  # unproven providers start neutral, not penalized
        return self.total_successes / self.total_calls


class EconomicAction(db.Model):
    """Core lifecycle record for one autonomous purchase. Mirrors AgentAction's role in
    the task control plane, but scoped to money movement: PROPOSED -> POLICY_CHECK ->
    APPROVED/REJECTED -> PAYMENT_PENDING -> PAID/PAYMENT_FAILED -> SERVICE_EXECUTING ->
    RESULT_RECEIVED/SERVICE_FAILED -> VERIFIED/VERIFICATION_FAILED."""
    __tablename__ = 'economic_actions'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)

    run_id = db.Column(db.String, db.ForeignKey('agent_runs.id'), nullable=True)
    action_id = db.Column(db.String, db.ForeignKey('agent_actions.id'), nullable=True)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'), nullable=False)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=True)

    capability = db.Column(db.String, nullable=False)
    task_description = db.Column(db.Text)  # the agent's own goal/task at time of purchase
    reason = db.Column(db.Text)  # why the agent decided it needed this capability

    provider_id = db.Column(db.String, db.ForeignKey('capability_providers.id'), nullable=True)
    requested_amount_usdc = db.Column(db.Numeric(18, 6), nullable=False)
    currency = db.Column(db.String, default='USDC')

    constraints = db.Column(JSONB, default=dict)  # {max_cost_usdc, max_latency_ms}
    status = db.Column(db.String, default='PROPOSED')
    policy_decision = db.Column(JSONB, default=dict)  # {decision, reasons: [...]}

    service_result = db.Column(JSONB, default=dict)
    verification_status = db.Column(db.String, nullable=True)
    verification_notes = db.Column(db.Text, nullable=True)
    quality_score = db.Column(db.Float, nullable=True)
    latency_ms = db.Column(db.Integer, nullable=True)

    error_message = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    provider = db.relationship('CapabilityProvider')


class PaymentTransaction(db.Model):
    """The Circle payment execution record — one per settlement attempt, created before
    the Circle call and updated after, so a crash mid-call still leaves an audit trail
    of "we intended to pay X" (see service.execute_payment)."""
    __tablename__ = 'payment_transactions'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)

    economic_action_id = db.Column(db.String, db.ForeignKey('economic_actions.id'), nullable=False)
    wallet_id = db.Column(db.String, db.ForeignKey('agent_wallets.id'), nullable=False)

    circle_transaction_id = db.Column(db.String, nullable=True)
    transaction_hash = db.Column(db.String, nullable=True)
    from_address = db.Column(db.String, nullable=True)
    to_address = db.Column(db.String, nullable=True)
    chain = db.Column(db.String, nullable=False)

    amount_usdc = db.Column(db.Numeric(18, 6), nullable=False)
    status = db.Column(db.String, default='PENDING')
    explorer_url = db.Column(db.String, nullable=True)
    is_simulated = db.Column(db.Boolean, default=True)
    error_message = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    confirmed_at = db.Column(db.DateTime, nullable=True)


class EconomicEvidence(db.Model):
    """User-facing evidence of one autonomous purchase — the answer to "what did Ora
    buy, why, from whom, for how much, and did it help?" One row per EconomicAction,
    written only once the action reaches a terminal (paid) state."""
    __tablename__ = 'economic_evidence'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)

    economic_action_id = db.Column(db.String, db.ForeignKey('economic_actions.id'), nullable=False, unique=True)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'), nullable=False)

    user_goal = db.Column(db.Text)
    capability = db.Column(db.String, nullable=False)
    provider_name = db.Column(db.String, nullable=False)
    price_usdc = db.Column(db.Numeric(18, 6), nullable=False)

    payment_transaction_id = db.Column(db.String, db.ForeignKey('payment_transactions.id'), nullable=True)
    circle_wallet_address = db.Column(db.String, nullable=True)
    circle_transaction_id = db.Column(db.String, nullable=True)
    transaction_hash = db.Column(db.String, nullable=True)
    explorer_url = db.Column(db.String, nullable=True)

    service_result_summary = db.Column(JSONB, default=dict)
    verification_status = db.Column(db.String, nullable=True)
    quality_score = db.Column(db.Float, nullable=True)
    latency_ms = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
