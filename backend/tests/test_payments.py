"""Agent Economy: policy engine, provider discovery/selection, and the end-to-end
acquire_capability lifecycle (policy -> Circle payment -> provider call -> verification
-> evidence), all run against CircleClient's simulation mode (no CIRCLE_API_KEY set in
TestConfig, so every wallet/transfer is a deterministic local fixture)."""
from decimal import Decimal

from flask_jwt_extended import create_access_token

from app.core.extensions import db
from app.auth.models import User
from app.workspaces.models import Workspace
from app.agents.execution_context import ExecutionContext, execution_context
from app.payments import discovery, policy as policy_engine, service
from app.payments.economic_control import EconomicActionStatus, PolicyDecision
from app.payments.models import (
    AgentWallet, CapabilityProvider, EconomicAction, EconomicEvidence, PaymentTransaction,
)


def _make_user(email="econ_user@example.com"):
    from app.core.security import hash_password
    user = User(email=email, name="Econ User", password_hash=hash_password("pw"), email_verified=True)
    db.session.add(user)
    db.session.commit()
    return user


def _make_workspace(owner_id, name="Econ Workspace"):
    ws = Workspace(name=name, context="personal", type="project", owner_id=owner_id)
    db.session.add(ws)
    db.session.commit()
    return ws


def _seed_provider(**overrides):
    defaults = dict(
        capability="competitor_research", name="Test Provider", provider="test.provider",
        description="test", endpoint="sim://providers/test/report",
        price_usdc=Decimal("0.05"), estimated_latency_ms=2000, chain="MATIC-AMOY",
    )
    defaults.update(overrides)
    provider = CapabilityProvider(**defaults)
    db.session.add(provider)
    db.session.commit()
    return provider


def _ctx(user, workspace):
    return ExecutionContext(request_id="test-req", user_id=user.id, workspace_id=workspace.id)


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------

def test_select_provider_prefers_higher_blended_score_over_cheapest(app, db):
    with app.app_context():
        cheap_but_slow_unproven = _seed_provider(
            name="Cheap", provider="cheap.io", price_usdc=Decimal("0.01"), estimated_latency_ms=20000,
        )
        cheap_but_slow_unproven.total_calls = 50
        cheap_but_slow_unproven.total_successes = 10  # 20% success rate — bad track record
        fast_reliable = _seed_provider(
            name="Reliable", provider="reliable.io", price_usdc=Decimal("0.08"), estimated_latency_ms=1000,
        )
        fast_reliable.total_calls = 50
        fast_reliable.total_successes = 49  # 98% success rate
        db.session.commit()

        chosen = discovery.select_provider([cheap_but_slow_unproven, fast_reliable])
        assert chosen.provider == "reliable.io"


def test_select_provider_respects_max_cost_constraint(app, db):
    with app.app_context():
        cheap = _seed_provider(name="Cheap", provider="cheap.io", price_usdc=Decimal("0.01"))
        expensive = _seed_provider(name="Pricey", provider="pricey.io", price_usdc=Decimal("5.00"))
        chosen = discovery.select_provider([cheap, expensive], max_cost_usdc=0.10)
        assert chosen.provider == "cheap.io"


def test_select_provider_returns_none_when_nothing_qualifies(app, db):
    with app.app_context():
        provider = _seed_provider(price_usdc=Decimal("1.00"))
        assert discovery.select_provider([provider], max_cost_usdc=0.01) is None


# ---------------------------------------------------------------------------
# Policy engine
# ---------------------------------------------------------------------------

def test_policy_approves_small_payment_within_defaults(app, db):
    with app.app_context():
        user = _make_user()
        ws = _make_workspace(user.id)
        provider = _seed_provider(price_usdc=Decimal("0.05"))
        wallet = service.ensure_wallet(ws.id)

        result = policy_engine.evaluate_policy(
            workspace_id=ws.id, wallet=wallet, capability="competitor_research",
            provider=provider, amount_usdc=0.05,
        )
        assert result.decision == PolicyDecision.APPROVED.value


def test_policy_requires_approval_above_auto_threshold(app, db):
    with app.app_context():
        user = _make_user("threshold_user@example.com")
        ws = _make_workspace(user.id, "Threshold WS")
        provider = _seed_provider(price_usdc=Decimal("0.50"))
        wallet = service.ensure_wallet(ws.id)
        p = policy_engine.get_or_create_policy(ws.id)
        p.per_transaction_limit_usdc = Decimal("1.0")
        p.daily_limit_usdc = Decimal("5.0")
        p.auto_approve_threshold_usdc = Decimal("0.10")
        db.session.commit()

        result = policy_engine.evaluate_policy(
            workspace_id=ws.id, wallet=wallet, capability="competitor_research",
            provider=provider, amount_usdc=0.50,
        )
        assert result.decision == PolicyDecision.REQUIRES_USER_APPROVAL.value


def test_policy_rejects_over_per_transaction_limit(app, db):
    with app.app_context():
        user = _make_user("overlimit_user@example.com")
        ws = _make_workspace(user.id, "Overlimit WS")
        provider = _seed_provider(price_usdc=Decimal("2.00"))
        wallet = service.ensure_wallet(ws.id)
        p = policy_engine.get_or_create_policy(ws.id)
        p.per_transaction_limit_usdc = Decimal("1.0")
        db.session.commit()

        result = policy_engine.evaluate_policy(
            workspace_id=ws.id, wallet=wallet, capability="competitor_research",
            provider=provider, amount_usdc=2.00,
        )
        assert result.decision == PolicyDecision.REJECTED.value
        assert any("per-transaction limit" in r for r in result.reasons)


def test_policy_rejects_when_emergency_stop_active(app, db):
    with app.app_context():
        user = _make_user("estop_user@example.com")
        ws = _make_workspace(user.id, "Estop WS")
        provider = _seed_provider(price_usdc=Decimal("0.01"))
        wallet = service.ensure_wallet(ws.id)
        p = policy_engine.get_or_create_policy(ws.id)
        p.emergency_stop = True
        db.session.commit()

        result = policy_engine.evaluate_policy(
            workspace_id=ws.id, wallet=wallet, capability="competitor_research",
            provider=provider, amount_usdc=0.01,
        )
        assert result.decision == PolicyDecision.REJECTED.value


def test_policy_rejects_blocked_provider(app, db):
    with app.app_context():
        user = _make_user("blocked_user@example.com")
        ws = _make_workspace(user.id, "Blocked WS")
        provider = _seed_provider(price_usdc=Decimal("0.01"), provider="blocked.io")
        wallet = service.ensure_wallet(ws.id)
        p = policy_engine.get_or_create_policy(ws.id)
        p.blocked_providers = ["blocked.io"]
        db.session.commit()

        result = policy_engine.evaluate_policy(
            workspace_id=ws.id, wallet=wallet, capability="competitor_research",
            provider=provider, amount_usdc=0.01,
        )
        assert result.decision == PolicyDecision.REJECTED.value


# ---------------------------------------------------------------------------
# End-to-end acquire_capability (simulation mode)
# ---------------------------------------------------------------------------

def test_acquire_capability_end_to_end_succeeds_and_records_evidence(app, db):
    with app.app_context():
        user = _make_user("e2e_user@example.com")
        ws = _make_workspace(user.id, "E2E WS")
        _seed_provider(price_usdc=Decimal("0.05"))
        p = policy_engine.get_or_create_policy(ws.id)
        p.auto_approve_threshold_usdc = Decimal("1.0")  # allow this to auto-approve
        db.session.commit()

        ctx = _ctx(user, ws)
        with execution_context(ctx):
            result = service.acquire_capability(
                capability="competitor_research", task="research my top competitors",
                reason="user asked for competitor research",
            )

        assert result["success"] is True, result
        action = EconomicAction.query.filter_by(workspace_id=ws.id).first()
        assert action.status == EconomicActionStatus.VERIFIED.value
        assert action.verification_status == "VERIFIED"

        txn = PaymentTransaction.query.filter_by(economic_action_id=action.id).first()
        assert txn.status == "CONFIRMED"
        assert txn.is_simulated is True

        evidence = EconomicEvidence.query.filter_by(economic_action_id=action.id).first()
        assert evidence is not None
        assert evidence.provider_name == "Test Provider"

        wallet = AgentWallet.query.filter_by(workspace_id=ws.id).first()
        assert wallet.simulated_balance_usdc < Decimal("10.0")  # payment deducted


def test_acquire_capability_rejects_over_daily_limit(app, db):
    with app.app_context():
        user = _make_user("daily_user@example.com")
        ws = _make_workspace(user.id, "Daily WS")
        _seed_provider(price_usdc=Decimal("2.00"))
        p = policy_engine.get_or_create_policy(ws.id)
        p.daily_limit_usdc = Decimal("1.0")
        db.session.commit()

        ctx = _ctx(user, ws)
        with execution_context(ctx):
            result = service.acquire_capability(capability="competitor_research", task="research")

        assert result["success"] is False
        assert "policy" in result["error"].lower()
        action = EconomicAction.query.filter_by(workspace_id=ws.id).first()
        assert action.status == EconomicActionStatus.REJECTED.value


def test_acquire_capability_pauses_for_manual_approval_then_approve_completes_it(app, db):
    with app.app_context():
        user = _make_user("approve_user@example.com")
        ws = _make_workspace(user.id, "Approve WS")
        _seed_provider(price_usdc=Decimal("0.50"))
        p = policy_engine.get_or_create_policy(ws.id)
        p.auto_approve_threshold_usdc = Decimal("0.10")
        p.per_transaction_limit_usdc = Decimal("1.0")
        p.daily_limit_usdc = Decimal("5.0")
        db.session.commit()

        ctx = _ctx(user, ws)
        with execution_context(ctx):
            result = service.acquire_capability(capability="competitor_research", task="research")

        assert result["success"] is False
        action = EconomicAction.query.filter_by(workspace_id=ws.id).first()
        assert action.status == EconomicActionStatus.POLICY_CHECK.value
        assert action.policy_decision["decision"] == PolicyDecision.REQUIRES_USER_APPROVAL.value

        with execution_context(ctx):
            approve_result = service.approve_pending_action(action.id)

        assert approve_result["success"] is True, approve_result
        db.session.refresh(action)
        assert action.status == EconomicActionStatus.VERIFIED.value


def test_acquire_capability_fails_cleanly_when_no_provider_registered(app, db):
    with app.app_context():
        user = _make_user("noprov_user@example.com")
        ws = _make_workspace(user.id, "NoProvider WS")
        ctx = _ctx(user, ws)
        with execution_context(ctx):
            result = service.acquire_capability(capability="nonexistent_capability", task="do the thing")
        assert result["success"] is False
        assert "no allowed provider" in result["error"].lower()


# ---------------------------------------------------------------------------
# HTTP surface (auth + workspace scoping)
# ---------------------------------------------------------------------------

def test_wallet_endpoint_requires_workspace_access(app, client, db):
    with app.app_context():
        owner = _make_user("wallet_owner@example.com")
        ws = _make_workspace(owner.id, "HTTP WS")
        stranger = _make_user("stranger@example.com")
        stranger_token = create_access_token(identity=stranger.id)
        ws_id = ws.id

    resp = client.get(f"/api/v2/payments/workspaces/{ws_id}/wallet",
                       headers={"Authorization": f"Bearer {stranger_token}"})
    assert resp.status_code == 403


def test_create_wallet_and_read_it_back_over_http(app, client, db):
    with app.app_context():
        owner = _make_user("http_wallet_owner@example.com")
        ws = _make_workspace(owner.id, "HTTP Wallet WS")
        token = create_access_token(identity=owner.id)
        ws_id = ws.id

    resp = client.post(f"/api/v2/payments/workspaces/{ws_id}/wallet",
                        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["isSimulated"] is True
    assert body["address"].startswith("0x")

    resp = client.get(f"/api/v2/payments/workspaces/{ws_id}/wallet",
                       headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.get_json()["exists"] is True
