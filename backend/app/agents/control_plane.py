"""Deterministic control-plane primitives for agent-triggered work.

The LLM may propose actions, but application code owns these states and policies.
"""
from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any


class AgentRunStatus(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    WAITING_FOR_CONFIRMATION = "WAITING_FOR_CONFIRMATION"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ActionStatus(str, Enum):
    PROPOSED = "PROPOSED"
    WAITING_FOR_CONFIRMATION = "WAITING_FOR_CONFIRMATION"
    APPROVED = "APPROVED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    SKIPPED = "SKIPPED"


class ExecutionStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class VerificationStatus(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    RECONCILING = "RECONCILING"


class ErrorClass(str, Enum):
    VALIDATION = "VALIDATION"
    AUTHORIZATION = "AUTHORIZATION"
    AUTHENTICATION = "AUTHENTICATION"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    RATE_LIMIT = "RATE_LIMIT"
    TIMEOUT = "TIMEOUT"
    TRANSIENT = "TRANSIENT"
    PERMANENT = "PERMANENT"
    UNKNOWN = "UNKNOWN"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


ACTION_METADATA: dict[str, dict[str, Any]] = {
    "task.create": {"risk": RiskLevel.MEDIUM, "mutation": True, "confirmation_required": False},
    "task.bulk_create": {"risk": RiskLevel.MEDIUM, "mutation": True, "confirmation_required": False},
    "task.update": {
        "risk": RiskLevel.MEDIUM, "mutation": True, "confirmation_required": False,
        "reversible": True, "compensation_action_type": "task.restore",
    },
    "task.delete": {"risk": RiskLevel.HIGH, "mutation": True, "confirmation_required": True},
    "project.create": {"risk": RiskLevel.MEDIUM, "mutation": True, "confirmation_required": False},
    "project.update": {"risk": RiskLevel.MEDIUM, "mutation": True, "confirmation_required": False},
    "project.delete": {"risk": RiskLevel.HIGH, "mutation": True, "confirmation_required": True},
    "initiative.create": {"risk": RiskLevel.MEDIUM, "mutation": True, "confirmation_required": False},
    "note.create": {"risk": RiskLevel.LOW, "mutation": True, "confirmation_required": False},
    "plan.apply": {"risk": RiskLevel.HIGH, "mutation": True, "confirmation_required": True},
    "milestone.create": {"risk": RiskLevel.MEDIUM, "mutation": True, "confirmation_required": False},
    "milestone.update": {"risk": RiskLevel.MEDIUM, "mutation": True, "confirmation_required": False},
    "milestone.delete": {"risk": RiskLevel.HIGH, "mutation": True, "confirmation_required": True},
    "sprint.create": {"risk": RiskLevel.MEDIUM, "mutation": True, "confirmation_required": False},
    "sprint.update": {"risk": RiskLevel.MEDIUM, "mutation": True, "confirmation_required": False},
    "sprint.delete": {"risk": RiskLevel.HIGH, "mutation": True, "confirmation_required": True},
    "calendar.event.create": {
        "risk": RiskLevel.MEDIUM, "mutation": True, "confirmation_required": False,
        "reversible": True, "compensation_action_type": "calendar.event.unschedule",
    },
    "calendar.event.update": {
        "risk": RiskLevel.MEDIUM, "mutation": True, "confirmation_required": False,
        "reversible": True, "compensation_action_type": "calendar.event.restore",
    },
    "calendar.event.delete": {"risk": RiskLevel.HIGH, "mutation": True, "confirmation_required": True},
    "calendar.event.unschedule": {"risk": RiskLevel.MEDIUM, "mutation": True, "confirmation_required": False},
    "calendar.event.restore": {"risk": RiskLevel.MEDIUM, "mutation": True, "confirmation_required": False},
    "calendar.auto_schedule": {"risk": RiskLevel.HIGH, "mutation": True, "confirmation_required": True},
    "calendar.schedule_module_milestones": {"risk": RiskLevel.HIGH, "mutation": True, "confirmation_required": True},
    "schedule.apply": {"risk": RiskLevel.HIGH, "mutation": True, "confirmation_required": True},
    "schedule.revise": {"risk": RiskLevel.HIGH, "mutation": True, "confirmation_required": True},
    "action.undo": {"risk": RiskLevel.MEDIUM, "mutation": True, "confirmation_required": False},
    "task_dependency.create": {"risk": RiskLevel.MEDIUM, "mutation": True, "confirmation_required": False},
    "task_dependency.delete": {"risk": RiskLevel.MEDIUM, "mutation": True, "confirmation_required": False},
}


def action_metadata(action_type: str) -> dict[str, Any]:
    return ACTION_METADATA.get(
        action_type,
        {"risk": RiskLevel.MEDIUM, "mutation": True, "confirmation_required": False},
    )


def normalize_for_fingerprint(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: normalize_for_fingerprint(value[k]) for k in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [normalize_for_fingerprint(v) for v in value]
    return value


def request_fingerprint(action_type: str, workspace_id: str, args: dict[str, Any]) -> str:
    payload = {
        "action_type": action_type,
        "workspace_id": workspace_id,
        "args": normalize_for_fingerprint(args),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def classify_error(message: str | None) -> ErrorClass:
    text = (message or "").lower()
    if "forbidden" in text or "unauthorized" in text or "not authorized" in text:
        return ErrorClass.AUTHORIZATION
    if "not found" in text:
        return ErrorClass.NOT_FOUND
    if "validation" in text or "invalid" in text or "required" in text or "must be" in text or "cannot" in text:
        return ErrorClass.VALIDATION
    if "conflict" in text or "already exists" in text:
        return ErrorClass.CONFLICT
    if "timeout" in text or "timed out" in text:
        return ErrorClass.TIMEOUT
    return ErrorClass.UNKNOWN
