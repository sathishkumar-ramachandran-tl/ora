"""Deterministic executor for agent-triggered mutations.

This module is intentionally free of LLM logic. It records user-visible Actions and
concrete ToolExecution attempts, then calls reusable domain functions.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Callable, Optional

from sqlalchemy.exc import SQLAlchemyError

from ..core.extensions import db
from .control_plane import (
    ActionStatus,
    AgentRunStatus,
    ExecutionStatus,
    VerificationStatus,
    ErrorClass,
    action_metadata,
    classify_error,
    request_fingerprint,
)
from .execution_context import ExecutionContext, get_execution_context
from .models import AgentAction, AgentRun, AgentToolCall


NON_RETRYABLE = {
    ErrorClass.VALIDATION.value,
    ErrorClass.AUTHORIZATION.value,
    ErrorClass.AUTHENTICATION.value,
    ErrorClass.NOT_FOUND.value,
    ErrorClass.CONFLICT.value,
    ErrorClass.PERMANENT.value,
}
MAX_TOOL_CALLS_PER_RUN = 20


def create_agent_run(ctx: ExecutionContext, status: str = AgentRunStatus.RUNNING.value) -> AgentRun:
    run = AgentRun(
        id=ctx.run_id or str(uuid.uuid4()),
        request_id=ctx.request_id,
        session_id=ctx.session_id,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        status=status,
        started_at=datetime.utcnow(),
    )
    db.session.add(run)
    db.session.commit()
    return run


def ensure_agent_run(ctx: ExecutionContext) -> AgentRun:
    run = db.session.get(AgentRun, ctx.run_id) if ctx.run_id else None
    if run:
        return run
    return create_agent_run(ctx)


def _resource_type(action_type: str) -> str:
    return action_type.rsplit(".", 1)[0]


def _action_result(action: AgentAction) -> Optional[dict]:
    after = action.after_state or {}
    result = after.get("result")
    return result if isinstance(result, dict) else None


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _update_run_status(run_id: str) -> None:
    run = db.session.get(AgentRun, run_id)
    if not run:
        return
    actions = AgentAction.query.filter_by(run_id=run_id).all()
    if not actions:
        return

    statuses = {a.status for a in actions}
    if any(s == ActionStatus.WAITING_FOR_CONFIRMATION.value for s in statuses):
        run.status = AgentRunStatus.WAITING_FOR_CONFIRMATION.value
        return
    if all(s == ActionStatus.SUCCEEDED.value for s in statuses):
        run.status = AgentRunStatus.COMPLETED.value
        run.completed_at = datetime.utcnow()
        return
    if any(s == ActionStatus.SUCCEEDED.value for s in statuses) and any(
        s in {ActionStatus.FAILED.value, ActionStatus.UNKNOWN.value, ActionStatus.SKIPPED.value}
        for s in statuses
    ):
        run.status = AgentRunStatus.PARTIALLY_COMPLETED.value
        run.completed_at = datetime.utcnow()
        return
    if all(s in {ActionStatus.FAILED.value, ActionStatus.SKIPPED.value} for s in statuses):
        run.status = AgentRunStatus.FAILED.value
        run.completed_at = datetime.utcnow()


def _create_action(
    ctx: ExecutionContext,
    action_type: str,
    args: dict[str, Any],
    action_id: Optional[str] = None,
    parent_action_id: Optional[str] = None,
) -> AgentAction:
    run = ensure_agent_run(ctx)
    existing = db.session.get(AgentAction, action_id) if action_id else None
    if existing:
        return existing

    metadata = action_metadata(action_type)
    action = AgentAction(
        id=action_id or str(uuid.uuid4()),
        run_id=run.id,
        parent_action_id=parent_action_id,
        action_type=action_type,
        resource_type=_resource_type(action_type),
        status=ActionStatus.PROPOSED.value,
        risk_level=metadata["risk"].value if hasattr(metadata["risk"], "value") else metadata["risk"],
        confirmation_required=bool(metadata["confirmation_required"]),
        proposed_args=_json_safe(args),
        request_fingerprint=request_fingerprint(action_type, ctx.workspace_id, args),
    )
    action.idempotency_key = f"act_{action.id}"
    db.session.add(action)
    db.session.commit()
    return action


def execute_action(
    action_type: str,
    tool_name: str,
    args: dict[str, Any],
    invoke: Callable[[], dict],
    *,
    action_id: Optional[str] = None,
    parent_action_id: Optional[str] = None,
    verify: Optional[Callable[[dict], bool]] = None,
    before: Optional[Callable[[], dict | None]] = None,
) -> dict:
    ctx = get_execution_context(required=True)
    run = ensure_agent_run(ctx)
    action = _create_action(ctx, action_type, args, action_id, parent_action_id)

    if action.status == ActionStatus.SUCCEEDED.value:
        existing = _action_result(action)
        if existing is not None:
            return {"success": True, "data": existing, "error": None}

    if action.status == ActionStatus.FAILED.value and action.after_state:
        error_class = action.after_state.get("error_class")
        if error_class in NON_RETRYABLE:
            return {"success": False, "data": None, "error": action.after_state.get("error") or "Action failed"}

    if action.confirmation_required and action.status in {
        ActionStatus.PROPOSED.value,
        ActionStatus.WAITING_FOR_CONFIRMATION.value,
    }:
        action.status = ActionStatus.WAITING_FOR_CONFIRMATION.value
        db.session.commit()
        _update_run_status(action.run_id)
        return {"success": False, "data": None, "error": "Confirmation required before executing this action"}

    if before is not None and not action.before_state:
        action.before_state = before() or {}
    metadata = action_metadata(action_type)
    action.reversible = bool(metadata.get("reversible", action.reversible))
    action.compensation_action_type = metadata.get("compensation_action_type") or action.compensation_action_type
    action.status = ActionStatus.RUNNING.value
    db.session.commit()

    if AgentToolCall.query.filter_by(run_id=run.id).count() >= MAX_TOOL_CALLS_PER_RUN:
        action.status = ActionStatus.FAILED.value
        action.after_state = {
            "error": "Tool execution budget exceeded",
            "error_class": ErrorClass.PERMANENT.value,
        }
        action.completed_at = datetime.utcnow()
        db.session.commit()
        _update_run_status(action.run_id)
        return {"success": False, "data": None, "error": "Tool execution budget exceeded"}

    attempt_number = AgentToolCall.query.filter_by(action_id=action.id).count() + 1
    tool_call = AgentToolCall(
        session_id=ctx.session_id,
        run_id=run.id,
        action_id=action.id,
        tool_name=tool_name,
        tool_args=_json_safe(args),
        status="running",
        execution_status=ExecutionStatus.RUNNING.value,
        verification_status=VerificationStatus.UNVERIFIED.value,
        attempt_number=attempt_number,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        started_at=datetime.utcnow(),
    )
    db.session.add(tool_call)
    db.session.commit()

    try:
        result = invoke()
    except SQLAlchemyError as exc:
        db.session.rollback()
        result = {"success": False, "data": None, "error": f"Database error: {exc.__class__.__name__}"}
    except Exception as exc:
        result = {"success": False, "data": None, "error": str(exc)}

    tool_call.completed_at = datetime.utcnow()
    tool_call.tool_result = result

    if result.get("success"):
        verified = True if verify is None else bool(verify(result["data"]))
        tool_call.status = "success" if verified else "error"
        tool_call.execution_status = ExecutionStatus.SUCCEEDED.value
        tool_call.verification_status = (
            VerificationStatus.VERIFIED.value if verified else VerificationStatus.FAILED.value
        )
        if verified:
            tool_call.verified_at = datetime.utcnow()
            action.status = ActionStatus.SUCCEEDED.value
            action.resource_id = _extract_resource_id(result["data"])
            action.after_state = {"result": result["data"]}
        else:
            action.status = ActionStatus.UNKNOWN.value
            action.after_state = {
                "result": result["data"],
                "error": "Verification failed",
                "error_class": ErrorClass.UNKNOWN.value,
            }
            tool_call.error_class = ErrorClass.UNKNOWN.value
            tool_call.error_message = "Verification failed"
    else:
        error = result.get("error") or "Tool execution failed"
        error_class = classify_error(error).value
        tool_call.status = "error"
        tool_call.execution_status = ExecutionStatus.FAILED.value
        tool_call.verification_status = VerificationStatus.FAILED.value
        tool_call.error_class = error_class
        tool_call.error_message = error
        action.status = ActionStatus.FAILED.value
        action.after_state = {"error": error, "error_class": error_class}

    action.completed_at = datetime.utcnow()
    db.session.commit()
    _update_run_status(action.run_id)
    return result


def _extract_resource_id(data: Any) -> Optional[str]:
    if isinstance(data, dict):
        for key in ("id", "resource_id", "eventId", "deleted_task_id", "deleted_project_id"):
            value = data.get(key)
            if value:
                return str(value)
    return None
