"""Agent Economy API — /api/v2/payments/workspaces/<workspace_id>/*.

Every route enforces the same baseline as every other workspace-scoped surface in
Ora: `user_can_access_workspace` first (docs/ARCHITECTURE.md — object IDs alone are
never sufficient authorization), then, for endpoints that move money or change policy,
an additional payments.* permission check for organization-owned workspaces.

Nothing here calls Circle directly — everything goes through app/payments/service.py
and app/payments/circle_client.py.
"""
from __future__ import annotations

import uuid

from flask import Blueprint, g, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..agents.action_executor import create_agent_run
from ..agents.execution_context import ExecutionContext, execution_context
from ..core.authz import user_can_access_workspace
from ..core.extensions import db
from ..workspaces.models import Workspace
from . import policy as policy_engine, service
from .models import CapabilityProvider, EconomicAction, EconomicEvidence, PaymentTransaction

payments_bp = Blueprint("payments", __name__)


# ---------------------------------------------------------------------------
# Access helpers
# ---------------------------------------------------------------------------

def _load_workspace_or_403(workspace_id: str):
    user_id = get_jwt_identity()
    if not user_can_access_workspace(user_id, workspace_id):
        return None, (jsonify({"error": "Forbidden"}), 403)
    workspace = db.session.get(Workspace, workspace_id)
    if not workspace:
        return None, (jsonify({"error": "Workspace not found"}), 404)
    return workspace, None


def _can_manage(user_id: str, workspace: Workspace) -> bool:
    if workspace.owner_id == user_id:
        return True
    if workspace.organization_id:
        from ..organizations.permissions import check_permission
        return check_permission(user_id, workspace.organization_id, "payments.manage")
    return False


def _can_approve(user_id: str, workspace: Workspace) -> bool:
    if workspace.owner_id == user_id:
        return True
    if workspace.organization_id:
        from ..organizations.permissions import check_permission
        return (
            check_permission(user_id, workspace.organization_id, "payments.approve")
            or check_permission(user_id, workspace.organization_id, "payments.manage")
        )
    return False


def _ctx(workspace_id: str) -> ExecutionContext:
    return ExecutionContext(
        request_id=getattr(g, "request_id", None) or str(uuid.uuid4()),
        user_id=get_jwt_identity(),
        workspace_id=workspace_id,
        run_id=str(uuid.uuid4()),
    )


def _money(value) -> float:
    return float(value) if value is not None else None


def _serialize_action(action: EconomicAction) -> dict:
    provider = action.provider
    return {
        "id": action.id,
        "capability": action.capability,
        "task": action.task_description,
        "reason": action.reason,
        "provider": {"id": provider.id, "name": provider.name, "provider": provider.provider} if provider else None,
        "amountUsdc": _money(action.requested_amount_usdc),
        "status": action.status,
        "policyDecision": action.policy_decision,
        "verificationStatus": action.verification_status,
        "qualityScore": action.quality_score,
        "latencyMs": action.latency_ms,
        "errorMessage": action.error_message,
        "createdAt": action.created_at.isoformat() if action.created_at else None,
        "completedAt": action.completed_at.isoformat() if action.completed_at else None,
    }


def _serialize_provider(p: CapabilityProvider) -> dict:
    return {
        "id": p.id,
        "capability": p.capability,
        "name": p.name,
        "provider": p.provider,
        "description": p.description,
        "priceUsdc": _money(p.price_usdc),
        "currency": p.currency,
        "chain": p.chain,
        "estimatedLatencyMs": p.estimated_latency_ms,
        "successRate": p.success_rate,
        "isActive": p.is_active,
    }


def _serialize_transaction(t: PaymentTransaction) -> dict:
    return {
        "id": t.id,
        "economicActionId": t.economic_action_id,
        "amountUsdc": _money(t.amount_usdc),
        "status": t.status,
        "chain": t.chain,
        "transactionHash": t.transaction_hash,
        "explorerUrl": t.explorer_url,
        "isSimulated": t.is_simulated,
        "createdAt": t.created_at.isoformat() if t.created_at else None,
    }


# ---------------------------------------------------------------------------
# Wallet
# ---------------------------------------------------------------------------

@payments_bp.route("/workspaces/<workspace_id>/wallet", methods=["GET"])
@jwt_required()
def get_wallet(workspace_id):
    workspace, err = _load_workspace_or_403(workspace_id)
    if err:
        return err
    from .models import AgentWallet
    wallet = AgentWallet.query.filter_by(workspace_id=workspace_id).first()
    if not wallet:
        return jsonify({"exists": False})
    balance = service.get_wallet_balance(wallet)
    return jsonify({
        "exists": True,
        "id": wallet.id,
        "address": wallet.address,
        "blockchain": wallet.blockchain,
        "status": wallet.status,
        "isSimulated": wallet.is_simulated,
        "supportedChains": service.get_circle_client().supported_chains(),
        "balance": balance,
    })


@payments_bp.route("/workspaces/<workspace_id>/wallet", methods=["POST"])
@jwt_required()
def create_wallet(workspace_id):
    workspace, err = _load_workspace_or_403(workspace_id)
    if err:
        return err
    user_id = get_jwt_identity()
    if not _can_manage(user_id, workspace):
        return jsonify({"error": "Forbidden", "missing_permission": "payments.manage"}), 403

    wallet = service.ensure_wallet(workspace_id)
    balance = service.get_wallet_balance(wallet)
    return jsonify({
        "id": wallet.id, "address": wallet.address, "blockchain": wallet.blockchain,
        "status": wallet.status, "isSimulated": wallet.is_simulated, "balance": balance,
    }), 201


@payments_bp.route("/workspaces/<workspace_id>/transactions", methods=["GET"])
@jwt_required()
def list_transactions(workspace_id):
    _, err = _load_workspace_or_403(workspace_id)
    if err:
        return err
    txns = service.list_wallet_transactions(workspace_id)
    return jsonify([_serialize_transaction(t) for t in txns])


@payments_bp.route("/workspaces/<workspace_id>/spending-summary", methods=["GET"])
@jwt_required()
def spending_summary(workspace_id):
    _, err = _load_workspace_or_403(workspace_id)
    if err:
        return err
    return jsonify(policy_engine.spending_summary(workspace_id))


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

@payments_bp.route("/workspaces/<workspace_id>/policy", methods=["GET"])
@jwt_required()
def get_policy(workspace_id):
    _, err = _load_workspace_or_403(workspace_id)
    if err:
        return err
    p = policy_engine.get_or_create_policy(workspace_id)
    return jsonify({
        "perTransactionLimitUsdc": _money(p.per_transaction_limit_usdc),
        "dailyLimitUsdc": _money(p.daily_limit_usdc),
        "monthlyLimitUsdc": _money(p.monthly_limit_usdc),
        "autoApproveThresholdUsdc": _money(p.auto_approve_threshold_usdc),
        "allowedCapabilityCategories": p.allowed_capability_categories or [],
        "allowedProviders": p.allowed_providers or [],
        "blockedProviders": p.blocked_providers or [],
        "requireConfirmationAboveThreshold": p.require_confirmation_above_threshold,
        "emergencyStop": p.emergency_stop,
    })


_POLICY_FIELD_MAP = {
    "perTransactionLimitUsdc": "per_transaction_limit_usdc",
    "dailyLimitUsdc": "daily_limit_usdc",
    "monthlyLimitUsdc": "monthly_limit_usdc",
    "autoApproveThresholdUsdc": "auto_approve_threshold_usdc",
    "allowedCapabilityCategories": "allowed_capability_categories",
    "allowedProviders": "allowed_providers",
    "blockedProviders": "blocked_providers",
    "requireConfirmationAboveThreshold": "require_confirmation_above_threshold",
    "emergencyStop": "emergency_stop",
}


@payments_bp.route("/workspaces/<workspace_id>/policy", methods=["PATCH"])
@jwt_required()
def update_policy(workspace_id):
    workspace, err = _load_workspace_or_403(workspace_id)
    if err:
        return err
    user_id = get_jwt_identity()
    if not _can_manage(user_id, workspace):
        return jsonify({"error": "Forbidden", "missing_permission": "payments.manage"}), 403

    data = request.json or {}
    p = policy_engine.get_or_create_policy(workspace_id)
    for key, column in _POLICY_FIELD_MAP.items():
        if key in data:
            setattr(p, column, data[key])
    db.session.commit()
    return jsonify({"status": "updated"})


# ---------------------------------------------------------------------------
# Capabilities (discovery)
# ---------------------------------------------------------------------------

@payments_bp.route("/capabilities", methods=["GET"])
@jwt_required()
def list_capabilities():
    capability = request.args.get("capability")
    query = CapabilityProvider.query.filter_by(is_active=True)
    if capability:
        query = query.filter_by(capability=capability)
    providers = query.order_by(CapabilityProvider.capability, CapabilityProvider.price_usdc).all()
    return jsonify([_serialize_provider(p) for p in providers])


@payments_bp.route("/workspaces/<workspace_id>/capabilities/acquire", methods=["POST"])
@jwt_required()
def acquire_capability_manual(workspace_id):
    """Manual/demo trigger for the same pipeline an agent tool call would run — still
    fully policy-gated. Useful for testing the Agent Economy without going through a
    chat-driven agent run."""
    workspace, err = _load_workspace_or_403(workspace_id)
    if err:
        return err
    user_id = get_jwt_identity()
    if not _can_manage(user_id, workspace):
        return jsonify({"error": "Forbidden", "missing_permission": "payments.manage"}), 403

    data = request.json or {}
    capability = (data.get("capability") or "").strip()
    task = (data.get("task") or "").strip()
    if not capability or not task:
        return jsonify({"error": "capability and task are required"}), 400

    ctx = _ctx(workspace_id)
    create_agent_run(ctx)
    with execution_context(ctx):
        result = service.acquire_capability(
            capability=capability,
            task=task,
            reason=data.get("reason", ""),
            constraints={
                k: data[k] for k in ("max_cost_usdc", "max_latency_ms") if data.get(k) is not None
            },
        )
    status = 200 if result["success"] else 402
    return jsonify(result), status


# ---------------------------------------------------------------------------
# Economic actions (activity + evidence)
# ---------------------------------------------------------------------------

@payments_bp.route("/workspaces/<workspace_id>/economic-actions", methods=["GET"])
@jwt_required()
def list_economic_actions(workspace_id):
    _, err = _load_workspace_or_403(workspace_id)
    if err:
        return err
    actions = (
        EconomicAction.query.filter_by(workspace_id=workspace_id)
        .order_by(EconomicAction.created_at.desc())
        .limit(200)
        .all()
    )
    return jsonify([_serialize_action(a) for a in actions])


@payments_bp.route("/workspaces/<workspace_id>/economic-actions/<action_id>", methods=["GET"])
@jwt_required()
def get_economic_action(workspace_id, action_id):
    _, err = _load_workspace_or_403(workspace_id)
    if err:
        return err
    action = db.session.get(EconomicAction, action_id)
    if not action or action.workspace_id != workspace_id:
        return jsonify({"error": "Not found"}), 404
    evidence = EconomicEvidence.query.filter_by(economic_action_id=action.id).first()
    payload = _serialize_action(action)
    payload["evidence"] = None if not evidence else {
        "id": evidence.id,
        "userGoal": evidence.user_goal,
        "providerName": evidence.provider_name,
        "priceUsdc": _money(evidence.price_usdc),
        "circleWalletAddress": evidence.circle_wallet_address,
        "circleTransactionId": evidence.circle_transaction_id,
        "transactionHash": evidence.transaction_hash,
        "explorerUrl": evidence.explorer_url,
        "serviceResultSummary": evidence.service_result_summary,
        "verificationStatus": evidence.verification_status,
        "qualityScore": evidence.quality_score,
        "latencyMs": evidence.latency_ms,
        "createdAt": evidence.created_at.isoformat() if evidence.created_at else None,
    }
    return jsonify(payload)


@payments_bp.route("/workspaces/<workspace_id>/economic-actions/<action_id>/approve", methods=["POST"])
@jwt_required()
def approve_economic_action(workspace_id, action_id):
    workspace, err = _load_workspace_or_403(workspace_id)
    if err:
        return err
    user_id = get_jwt_identity()
    if not _can_approve(user_id, workspace):
        return jsonify({"error": "Forbidden", "missing_permission": "payments.approve"}), 403

    action = db.session.get(EconomicAction, action_id)
    if not action or action.workspace_id != workspace_id:
        return jsonify({"error": "Not found"}), 404

    ctx = _ctx(workspace_id)
    with execution_context(ctx):
        result = service.approve_pending_action(action_id)
    status = 200 if result["success"] else 400
    return jsonify(result), status


@payments_bp.route("/workspaces/<workspace_id>/economic-actions/<action_id>/reject", methods=["POST"])
@jwt_required()
def reject_economic_action(workspace_id, action_id):
    workspace, err = _load_workspace_or_403(workspace_id)
    if err:
        return err
    user_id = get_jwt_identity()
    if not _can_approve(user_id, workspace):
        return jsonify({"error": "Forbidden", "missing_permission": "payments.approve"}), 403

    action = db.session.get(EconomicAction, action_id)
    if not action or action.workspace_id != workspace_id:
        return jsonify({"error": "Not found"}), 404

    data = request.json or {}
    result = service.reject_pending_action(action_id, note=data.get("note", ""))
    status = 200 if result["success"] else 400
    return jsonify(result), status
