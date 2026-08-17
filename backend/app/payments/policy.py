"""Deterministic economic policy engine.

Every payment must pass evaluate_policy() before Circle is ever called. This is plain,
auditable Python — no model call, no LLM-influenced branching. The result is stored on
EconomicAction.policy_decision so a user can always see exactly why a purchase was
approved, blocked, or sent for manual approval.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ..core.extensions import db
from .economic_control import PolicyDecision
from .models import CapabilityProvider, EconomicPolicy, PaymentTransaction, EconomicAction


@dataclass
class PolicyResult:
    decision: str
    reasons: list[str] = field(default_factory=list)

    @property
    def approved(self) -> bool:
        return self.decision == PolicyDecision.APPROVED.value

    def to_dict(self) -> dict:
        return {"decision": self.decision, "reasons": self.reasons}


def get_or_create_policy(workspace_id: str) -> EconomicPolicy:
    policy = EconomicPolicy.query.filter_by(workspace_id=workspace_id).first()
    if policy:
        return policy
    # Conservative defaults: small per-transaction/day caps, low auto-approve threshold.
    # A workspace owner raises these explicitly via PATCH /policy — nothing here assumes
    # generous spending is safe by default.
    policy = EconomicPolicy(workspace_id=workspace_id)
    db.session.add(policy)
    db.session.commit()
    return policy


def _spent_since(workspace_id: str, since: datetime) -> float:
    rows = (
        db.session.query(PaymentTransaction.amount_usdc)
        .join(EconomicAction, EconomicAction.id == PaymentTransaction.economic_action_id)
        .filter(
            EconomicAction.workspace_id == workspace_id,
            PaymentTransaction.status == 'CONFIRMED',
            PaymentTransaction.created_at >= since,
        )
        .all()
    )
    return float(sum(float(r[0]) for r in rows))


def spending_summary(workspace_id: str) -> dict:
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    policy = get_or_create_policy(workspace_id)
    today = _spent_since(workspace_id, today_start)
    month = _spent_since(workspace_id, month_start)
    daily_limit = float(policy.daily_limit_usdc) if policy.daily_limit_usdc is not None else None
    return {
        "today_usdc": today,
        "month_usdc": month,
        "daily_limit_usdc": daily_limit,
        "monthly_limit_usdc": float(policy.monthly_limit_usdc) if policy.monthly_limit_usdc is not None else None,
        "remaining_today_usdc": (daily_limit - today) if daily_limit is not None else None,
    }


def evaluate_policy(
    *,
    workspace_id: str,
    wallet,  # AgentWallet | None
    capability: str,
    provider: CapabilityProvider,
    amount_usdc: float,
) -> PolicyResult:
    """The single choke point money must pass through. Every check is independent and
    all failing reasons are collected (not short-circuited) so a user/agent sees the
    full picture, e.g. "over daily limit AND provider not allowlisted" at once."""
    policy = get_or_create_policy(workspace_id)
    reasons: list[str] = []

    if policy.emergency_stop:
        reasons.append("Emergency spending stop is active for this workspace")
        return PolicyResult(PolicyDecision.REJECTED.value, reasons)

    if wallet is None:
        reasons.append("No agent wallet configured for this workspace")
        return PolicyResult(PolicyDecision.REJECTED.value, reasons)

    if policy.allowed_capability_categories:
        if capability not in policy.allowed_capability_categories:
            reasons.append(f"Capability '{capability}' is not in the workspace's allowed capability list")

    blocked_providers = set(policy.blocked_providers or [])
    if provider.id in blocked_providers or provider.provider in blocked_providers:
        reasons.append(f"Provider '{provider.provider}' is blocked by workspace policy")

    allowed_providers = set(policy.allowed_providers or [])
    if allowed_providers and provider.id not in allowed_providers and provider.provider not in allowed_providers:
        reasons.append(f"Provider '{provider.provider}' is not in the workspace's provider allowlist")

    per_tx_limit = float(policy.per_transaction_limit_usdc)
    if amount_usdc > per_tx_limit:
        reasons.append(f"${amount_usdc:.4f} exceeds the per-transaction limit of ${per_tx_limit:.4f}")

    summary = spending_summary(workspace_id)
    if summary["daily_limit_usdc"] is not None and summary["today_usdc"] + amount_usdc > summary["daily_limit_usdc"]:
        reasons.append(
            f"${amount_usdc:.4f} would exceed today's remaining budget "
            f"(${summary['daily_limit_usdc'] - summary['today_usdc']:.4f} left of ${summary['daily_limit_usdc']:.4f})"
        )
    if summary["monthly_limit_usdc"] is not None and summary["month_usdc"] + amount_usdc > summary["monthly_limit_usdc"]:
        reasons.append(
            f"${amount_usdc:.4f} would exceed this month's spending limit of ${summary['monthly_limit_usdc']:.4f}"
        )

    if reasons:
        return PolicyResult(PolicyDecision.REJECTED.value, reasons)

    auto_threshold = float(policy.auto_approve_threshold_usdc)
    if policy.require_confirmation_above_threshold and amount_usdc > auto_threshold:
        return PolicyResult(
            PolicyDecision.REQUIRES_USER_APPROVAL.value,
            [f"${amount_usdc:.4f} exceeds the auto-approve threshold of ${auto_threshold:.4f} — user confirmation required"],
        )

    return PolicyResult(PolicyDecision.APPROVED.value, [f"${amount_usdc:.4f} is within all configured limits"])
