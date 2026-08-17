"""Deterministic control-plane primitives for Ora's economic execution layer.

Mirrors app/agents/control_plane.py: the LLM may propose an economic action (which
capability to buy, from which provider, for how much) but application code owns every
state transition and the policy decision. Nothing here is inferred from model output.
"""
from __future__ import annotations

from enum import Enum


class WalletStatus(str, Enum):
    CREATING = "CREATING"
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"
    ERROR = "ERROR"


class PolicyDecision(str, Enum):
    APPROVED = "APPROVED"
    REQUIRES_USER_APPROVAL = "REQUIRES_USER_APPROVAL"
    REJECTED = "REJECTED"


class EconomicActionStatus(str, Enum):
    PROPOSED = "PROPOSED"
    POLICY_CHECK = "POLICY_CHECK"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAID = "PAID"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    SERVICE_EXECUTING = "SERVICE_EXECUTING"
    SERVICE_FAILED = "SERVICE_FAILED"
    RESULT_RECEIVED = "RESULT_RECEIVED"
    VERIFIED = "VERIFIED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    REFUND_PENDING = "REFUND_PENDING"
    CANCELLED = "CANCELLED"


# Statuses a run should treat as "this purchase is finished, one way or another" —
# used by service.py to stop retrying/advancing an EconomicAction.
TERMINAL_ACTION_STATUSES = {
    EconomicActionStatus.REJECTED.value,
    EconomicActionStatus.PAYMENT_FAILED.value,
    EconomicActionStatus.SERVICE_FAILED.value,
    EconomicActionStatus.VERIFIED.value,
    EconomicActionStatus.VERIFICATION_FAILED.value,
    EconomicActionStatus.REFUND_PENDING.value,
    EconomicActionStatus.CANCELLED.value,
}


class TransactionStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class VerificationOutcome(str, Enum):
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
