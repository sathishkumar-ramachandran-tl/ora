"""Orchestrates one autonomous capability purchase end to end.

acquire_capability() is the single entrypoint both the agent tool (tools/payment_tools.py)
and the manual API route (routes.py) call. It threads through, in order:

  discover_providers -> select_provider -> EconomicAction (PROPOSED)
  -> evaluate_policy (POLICY_CHECK) -> [REJECTED | needs approval | APPROVED]
  -> execute_payment via the existing ActionExecutor choke point (PAYMENT_PENDING -> PAID)
  -> call_provider (SERVICE_EXECUTING -> RESULT_RECEIVED | SERVICE_FAILED)
  -> verify_result (VERIFIED | VERIFICATION_FAILED)
  -> record_evidence

Every mutating step commits through SQLAlchemy directly except the payment itself,
which goes through agents.action_executor.execute_action so it gets the same
AgentAction audit row, idempotency, and verification hook every other agent mutation
gets — money movement is not a special, unaudited path.
"""
from __future__ import annotations

import hashlib
import logging
import time
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

import requests

from ..core.extensions import db
from ..agents.action_executor import execute_action
from ..agents.execution_context import ExecutionContext, get_execution_context
from .circle_client import CircleClientError, get_circle_client
from .discovery import discover_providers, select_provider
from .economic_control import EconomicActionStatus, PolicyDecision, WalletStatus
from .models import (
    AgentWallet, CapabilityProvider, EconomicAction, EconomicEvidence, PaymentTransaction,
)
from .policy import evaluate_policy, get_or_create_policy

logger = logging.getLogger(__name__)

SIMULATED_STARTING_BALANCE_USDC = Decimal("10.0")


def _ok(data) -> dict:
    return {"success": True, "data": data, "error": None}


def _fail(error: str) -> dict:
    return {"success": False, "data": None, "error": error}


def _fake_provider_address(provider_id: str) -> str:
    return "0x" + hashlib.sha256(f"provider:{provider_id}".encode("utf-8")).hexdigest()[:40]


def _log_activity(ctx: Optional[ExecutionContext], event_name: str, properties: dict) -> None:
    try:
        from ..analytics.models import ActivityLog
        db.session.add(ActivityLog(
            event_name=event_name,
            properties=properties,
            user_id=ctx.user_id if ctx else None,
            workspace_id=ctx.workspace_id if ctx else properties.get("workspace_id"),
            platform="agent_economy",
        ))
        db.session.commit()
    except Exception:
        logger.exception("economic_activity_log_failed", extra={"event_name": event_name})


# ---------------------------------------------------------------------------
# Wallet
# ---------------------------------------------------------------------------

def ensure_wallet(workspace_id: str) -> AgentWallet:
    """Get-or-create the workspace's Circle agent wallet. Idempotent."""
    wallet = AgentWallet.query.filter_by(workspace_id=workspace_id).first()
    if wallet and wallet.status == WalletStatus.ACTIVE.value:
        return wallet

    circle = get_circle_client()
    info = circle.create_wallet(workspace_id)

    if wallet is None:
        wallet = AgentWallet(workspace_id=workspace_id)
        db.session.add(wallet)

    wallet.circle_wallet_id = info.circle_wallet_id
    wallet.address = info.address
    wallet.blockchain = info.blockchain
    wallet.status = WalletStatus.ACTIVE.value
    wallet.is_simulated = info.is_simulated
    if wallet.is_simulated and not wallet.simulated_balance_usdc:
        wallet.simulated_balance_usdc = SIMULATED_STARTING_BALANCE_USDC
    db.session.commit()
    return wallet


def get_wallet_balance(wallet: AgentWallet) -> dict:
    circle = get_circle_client()
    return circle.get_balance(
        wallet.circle_wallet_id,
        simulated=wallet.is_simulated,
        simulated_balance=float(wallet.simulated_balance_usdc or 0),
    )


def list_wallet_transactions(workspace_id: str) -> list[PaymentTransaction]:
    wallet = AgentWallet.query.filter_by(workspace_id=workspace_id).first()
    if not wallet:
        return []
    return (
        PaymentTransaction.query
        .join(EconomicAction, EconomicAction.id == PaymentTransaction.economic_action_id)
        .filter(EconomicAction.workspace_id == workspace_id)
        .order_by(PaymentTransaction.created_at.desc())
        .all()
    )


# ---------------------------------------------------------------------------
# Provider call + verification (treats provider output as untrusted data)
# ---------------------------------------------------------------------------

def _simulate_provider_response(provider: CapabilityProvider, task_description: str) -> dict:
    return {
        "capability": provider.capability,
        "provider": provider.provider,
        "summary": f"{provider.name} completed '{provider.capability}' for: {task_description[:200]}",
        "content": {
            "findings": [
                f"Simulated finding #{i + 1} from {provider.name} relevant to: {task_description[:80]}"
                for i in range(3)
            ],
            "sources": [f"https://example.invalid/{provider.provider}/source-{i}" for i in range(2)],
        },
        "generated_at": datetime.utcnow().isoformat(),
    }


def call_provider(provider: CapabilityProvider, task_description: str) -> tuple[Optional[dict], int, Optional[str]]:
    """Invoke the external capability. Returns (result, latency_ms, error). `result` is
    treated as untrusted external data by the caller — it is never used to change
    policy/authorization, only stored and shown to the user after verification."""
    start = time.monotonic()
    try:
        if provider.endpoint.startswith("sim://"):
            result = _simulate_provider_response(provider, task_description)
        else:
            resp = requests.post(
                provider.endpoint,
                json={"task": task_description, "capability": provider.capability},
                timeout=15,
            )
            resp.raise_for_status()
            result = resp.json()
            if not isinstance(result, dict):
                return None, int((time.monotonic() - start) * 1000), "Provider returned a non-object response"
    except requests.RequestException as exc:
        return None, int((time.monotonic() - start) * 1000), f"Provider call failed: {exc}"
    except Exception as exc:  # noqa: BLE001 — provider I/O, must not crash the run
        return None, int((time.monotonic() - start) * 1000), f"Provider call failed: {exc}"

    return result, int((time.monotonic() - start) * 1000), None


def verify_result(action: EconomicAction, result: dict) -> tuple[bool, str, float]:
    """Confirm the purchase actually delivered something usable for the task — a
    successful blockchain payment alone is never treated as task success."""
    if not isinstance(result, dict) or not result:
        return False, "Provider returned an empty or malformed result", 0.0
    returned_capability = result.get("capability")
    if returned_capability and returned_capability != action.capability:
        return False, (
            f"Provider returned a result for '{returned_capability}', "
            f"not the requested '{action.capability}'"
        ), 0.0
    content = result.get("content") or result.get("summary")
    if not content:
        return False, "Provider result has no usable content field", 0.2
    quality = 0.9 if len(str(content)) > 40 else 0.6
    return True, "Result shape and capability match the request; content present", quality


# ---------------------------------------------------------------------------
# Core lifecycle
# ---------------------------------------------------------------------------

def _propose(ctx: ExecutionContext, capability: str, task: str, reason: str,
             provider: CapabilityProvider, constraints: dict) -> EconomicAction:
    action = EconomicAction(
        run_id=ctx.run_id,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        capability=capability,
        task_description=task,
        reason=reason,
        provider_id=provider.id,
        requested_amount_usdc=provider.price_usdc,
        constraints=constraints,
        status=EconomicActionStatus.PROPOSED.value,
    )
    db.session.add(action)
    db.session.commit()
    return action


def _record_evidence(action: EconomicAction, txn: Optional[PaymentTransaction],
                      wallet: Optional[AgentWallet], provider: CapabilityProvider) -> EconomicEvidence:
    evidence = EconomicEvidence(
        economic_action_id=action.id,
        workspace_id=action.workspace_id,
        user_goal=action.task_description,
        capability=action.capability,
        provider_name=provider.name,
        price_usdc=action.requested_amount_usdc,
        payment_transaction_id=txn.id if txn else None,
        circle_wallet_address=wallet.address if wallet else None,
        circle_transaction_id=txn.circle_transaction_id if txn else None,
        transaction_hash=txn.transaction_hash if txn else None,
        explorer_url=txn.explorer_url if txn else None,
        service_result_summary=action.service_result or {},
        verification_status=action.verification_status,
        quality_score=action.quality_score,
        latency_ms=action.latency_ms,
    )
    db.session.add(evidence)
    db.session.commit()
    return evidence


def _execute_payment(action: EconomicAction, wallet: AgentWallet, provider: CapabilityProvider) -> dict:
    """Runs the Circle payment through the existing ActionExecutor choke point, so it
    gets an AgentAction row, idempotency, and a verify() gate before being marked
    SUCCEEDED — exactly like every other agent-triggered mutation."""
    agent_action_id = action.action_id or str(uuid.uuid4())
    to_address = provider.wallet_address or _fake_provider_address(provider.id)
    amount = float(action.requested_amount_usdc)
    idem_key = f"econ_{action.id}"

    def invoke() -> dict:
        balance = get_wallet_balance(wallet)
        if balance["amount"] < amount:
            return _fail(f"Insufficient wallet balance: have ${balance['amount']:.4f}, need ${amount:.4f}")

        try:
            transfer = get_circle_client().create_payment(
                circle_wallet_id=wallet.circle_wallet_id,
                from_address=wallet.address,
                to_address=to_address,
                amount_usdc=amount,
                chain=provider.chain,
                idempotency_key=idem_key,
            )
        except CircleClientError as exc:
            return _fail(f"Circle payment failed: {exc}")

        txn = PaymentTransaction(
            economic_action_id=action.id,
            wallet_id=wallet.id,
            circle_transaction_id=transfer.circle_transaction_id,
            transaction_hash=transfer.transaction_hash,
            from_address=wallet.address,
            to_address=to_address,
            chain=provider.chain,
            amount_usdc=action.requested_amount_usdc,
            status=transfer.status,
            explorer_url=transfer.explorer_url,
            is_simulated=transfer.is_simulated,
            confirmed_at=datetime.utcnow() if transfer.status == "CONFIRMED" else None,
        )
        db.session.add(txn)

        if wallet.is_simulated and transfer.status == "CONFIRMED":
            wallet.simulated_balance_usdc = Decimal(str(wallet.simulated_balance_usdc or 0)) - Decimal(str(amount))
        db.session.commit()

        return _ok({
            "payment_transaction_id": txn.id,
            "status": transfer.status,
            "transaction_hash": transfer.transaction_hash,
        })

    def verify(data: dict) -> bool:
        return data.get("status") == "CONFIRMED"

    action.status = EconomicActionStatus.PAYMENT_PENDING.value
    db.session.commit()

    result = execute_action(
        "payment.capability.acquire", "acquire_capability",
        {"capability": action.capability, "provider_id": provider.id, "amount_usdc": amount},
        invoke, verify=verify, action_id=agent_action_id,
    )
    action.action_id = agent_action_id
    db.session.commit()
    return result


def _continue_from_approved(ctx: Optional[ExecutionContext], action: EconomicAction,
                             wallet: AgentWallet, provider: CapabilityProvider) -> dict:
    payment_result = _execute_payment(action, wallet, provider)
    txn_id = (payment_result.get("data") or {}).get("payment_transaction_id")
    txn = db.session.get(PaymentTransaction, txn_id) if txn_id else None

    if not payment_result["success"]:
        # invoke() itself failed (insufficient balance, Circle API error, ...) — no
        # PaymentTransaction row, or one that never reached Circle.
        action.status = EconomicActionStatus.PAYMENT_FAILED.value
        action.error_message = payment_result["error"]
        action.completed_at = datetime.utcnow()
        db.session.commit()
        _log_activity(ctx, "economic_action.payment_failed", {
            "economic_action_id": action.id, "capability": action.capability,
            "provider": provider.provider, "error": payment_result["error"],
        })
        return _fail(f"Payment failed: {payment_result['error']}")

    if not txn or txn.status != "CONFIRMED":
        # execute_action() returns invoke()'s result unchanged even when its verify()
        # callback fails (verification only affects the AgentAction row) — so a
        # PENDING/unconfirmed real-mode transfer would otherwise look identical to a
        # confirmed one here. Never proceed to pay the provider for an unconfirmed
        # transfer; simulation-mode transfers always confirm synchronously so this
        # only bites in real Circle async-settlement mode.
        action.status = EconomicActionStatus.PAYMENT_PENDING.value
        action.error_message = f"Payment not yet confirmed on-chain (status={txn.status if txn else 'unknown'})"
        db.session.commit()
        _log_activity(ctx, "economic_action.payment_pending", {
            "economic_action_id": action.id, "capability": action.capability,
            "provider": provider.provider, "transaction_status": txn.status if txn else None,
        })
        return _fail(
            "Payment submitted but not yet confirmed on-chain — check back on this "
            f"economic_action_id ({action.id}) once it settles"
        )

    action.status = EconomicActionStatus.PAID.value
    db.session.commit()

    action.status = EconomicActionStatus.SERVICE_EXECUTING.value
    db.session.commit()
    result, latency_ms, call_error = call_provider(provider, action.task_description or "")

    provider.total_calls = (provider.total_calls or 0) + 1

    if call_error:
        # Payment already settled but the service didn't deliver — land in
        # REFUND_PENDING (not a dead-end SERVICE_FAILED) so this is flagged for
        # reconciliation rather than silently treated as "nothing happened".
        action.status = EconomicActionStatus.REFUND_PENDING.value
        action.error_message = f"Service call failed after payment: {call_error}"
        action.latency_ms = latency_ms
        action.completed_at = datetime.utcnow()
        db.session.commit()
        _record_evidence(action, txn, wallet, provider)
        _log_activity(ctx, "economic_action.service_failed", {
            "economic_action_id": action.id, "capability": action.capability,
            "provider": provider.provider, "error": call_error,
        })
        return _fail(f"Provider '{provider.name}' failed to deliver the capability: {call_error}")

    action.service_result = result
    action.latency_ms = latency_ms
    action.status = EconomicActionStatus.RESULT_RECEIVED.value
    db.session.commit()

    verified, notes, quality = verify_result(action, result)
    action.verification_notes = notes
    action.quality_score = quality
    action.verification_status = "VERIFIED" if verified else "FAILED"
    action.status = EconomicActionStatus.VERIFIED.value if verified else EconomicActionStatus.VERIFICATION_FAILED.value
    action.completed_at = datetime.utcnow()
    if verified:
        provider.total_successes = (provider.total_successes or 0) + 1
    db.session.commit()

    evidence = _record_evidence(action, txn, wallet, provider)
    _log_activity(ctx, f"economic_action.{'verified' if verified else 'verification_failed'}", {
        "economic_action_id": action.id, "capability": action.capability,
        "provider": provider.provider, "amount_usdc": float(action.requested_amount_usdc),
        "quality_score": quality,
    })

    if not verified:
        return _fail(f"Purchased result failed verification: {notes}")

    return _ok({
        "economic_action_id": action.id,
        "evidence_id": evidence.id,
        "provider": provider.name,
        "amount_usdc": float(action.requested_amount_usdc),
        "result": result,
        "verification_notes": notes,
        "quality_score": quality,
        "transaction_hash": txn.transaction_hash if txn else None,
        "explorer_url": txn.explorer_url if txn else None,
    })


def acquire_capability(*, capability: str, task: str, reason: str = "",
                        constraints: Optional[dict] = None) -> dict:
    """Top-level orchestrator. Requires an active ExecutionContext (set by the trusted
    HTTP entrypoint) — capability purchases are never allowed outside a trusted,
    workspace-scoped agent run."""
    ctx = get_execution_context(required=True)
    constraints = constraints or {}
    max_cost = constraints.get("max_cost_usdc")
    max_latency = constraints.get("max_latency_ms")

    policy = get_or_create_policy(ctx.workspace_id)
    candidates = discover_providers(capability, workspace_policy=policy)
    if not candidates:
        _log_activity(ctx, "economic_action.capability_unavailable", {
            "capability": capability, "workspace_id": ctx.workspace_id,
        })
        return _fail(f"No allowed provider is registered for capability '{capability}'")

    provider = select_provider(candidates, max_cost_usdc=max_cost, max_latency_ms=max_latency)
    if provider is None:
        return _fail(
            f"No provider for '{capability}' satisfies the given constraints "
            f"(max_cost_usdc={max_cost}, max_latency_ms={max_latency})"
        )

    action = _propose(ctx, capability, task, reason, provider, constraints)
    _log_activity(ctx, "economic_action.proposed", {
        "economic_action_id": action.id, "capability": capability,
        "provider": provider.provider, "amount_usdc": float(provider.price_usdc),
    })

    wallet = ensure_wallet(ctx.workspace_id)
    action.status = EconomicActionStatus.POLICY_CHECK.value
    db.session.commit()

    decision = evaluate_policy(
        workspace_id=ctx.workspace_id, wallet=wallet, capability=capability,
        provider=provider, amount_usdc=float(provider.price_usdc),
    )
    action.policy_decision = decision.to_dict()
    db.session.commit()
    _log_activity(ctx, "economic_action.policy_check", {
        "economic_action_id": action.id, "decision": decision.decision, "reasons": decision.reasons,
    })

    if decision.decision == PolicyDecision.REJECTED.value:
        action.status = EconomicActionStatus.REJECTED.value
        action.completed_at = datetime.utcnow()
        db.session.commit()
        return _fail(f"Payment rejected by economic policy: {'; '.join(decision.reasons)}")

    if decision.decision == PolicyDecision.REQUIRES_USER_APPROVAL.value:
        # Stays in POLICY_CHECK — visible via GET /economic-actions, resolved through
        # POST /economic-actions/<id>/approve|reject. The agent must not force this
        # through; only an explicit user action can move it to APPROVED.
        db.session.commit()
        return _fail(
            f"Requires user approval before Ora can spend ${float(provider.price_usdc):.4f} "
            f"on '{capability}' from {provider.name} (economic_action_id={action.id})"
        )

    action.status = EconomicActionStatus.APPROVED.value
    db.session.commit()
    return _continue_from_approved(ctx, action, wallet, provider)


def approve_pending_action(action_id: str) -> dict:
    """Explicit user approval for an action stuck in POLICY_CHECK /
    REQUIRES_USER_APPROVAL. Re-validates the policy decision is still what it was —
    a user approving a stale decision after policy/limits changed underneath it is not
    honored blindly."""
    action = db.session.get(EconomicAction, action_id)
    if not action:
        return _fail("Economic action not found")
    if action.status != EconomicActionStatus.POLICY_CHECK.value:
        return _fail(f"Action is not awaiting approval (status={action.status})")
    if (action.policy_decision or {}).get("decision") != PolicyDecision.REQUIRES_USER_APPROVAL.value:
        return _fail("Action is not pending manual approval")

    provider = db.session.get(CapabilityProvider, action.provider_id) if action.provider_id else None
    if not provider or not provider.is_active:
        action.status = EconomicActionStatus.REJECTED.value
        action.completed_at = datetime.utcnow()
        db.session.commit()
        return _fail("Provider is no longer available")

    wallet = ensure_wallet(action.workspace_id)
    action.status = EconomicActionStatus.APPROVED.value
    db.session.commit()
    ctx = get_execution_context(required=False)
    return _continue_from_approved(ctx, action, wallet, provider)


def reject_pending_action(action_id: str, note: str = "") -> dict:
    action = db.session.get(EconomicAction, action_id)
    if not action:
        return _fail("Economic action not found")
    if action.status not in {EconomicActionStatus.POLICY_CHECK.value, EconomicActionStatus.PROPOSED.value}:
        return _fail(f"Action can no longer be rejected (status={action.status})")
    action.status = EconomicActionStatus.CANCELLED.value
    action.error_message = note or "Rejected by user"
    action.completed_at = datetime.utcnow()
    db.session.commit()
    return _ok({"economic_action_id": action.id, "status": action.status})
