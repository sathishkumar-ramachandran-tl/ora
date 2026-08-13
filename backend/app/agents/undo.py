"""Compensating-action undo for safe first-party operations."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from ..calendar.models import CalendarEvent
from ..calendar.service import CalendarService, serialize_event
from ..core.extensions import db
from ..tasks.models import Task
from ..tools import task_tools
from .action_executor import execute_action
from .control_plane import ActionStatus, ErrorClass
from .execution_context import get_execution_context
from .models import AgentAction


def undo_action(action_id: str) -> dict[str, Any]:
    ctx = get_execution_context(required=True)
    original = db.session.get(AgentAction, action_id)
    if not original or original.run_id is None:
        return {"success": False, "data": None, "error": "Action not found"}
    if not original.reversible:
        return {"success": False, "data": None, "error": "Action is not reversible"}
    if original.undo_action_id:
        undo = db.session.get(AgentAction, original.undo_action_id)
        return {
            "success": undo is not None and undo.status == ActionStatus.SUCCEEDED.value,
            "data": {"undoActionId": original.undo_action_id, "status": original.undo_status},
            "error": None if original.undo_status == ActionStatus.SUCCEEDED.value else "Action was already undone or undo is not available",
        }
    if original.action_type == "calendar.event.create":
        return _undo_calendar_create(ctx, original)
    if original.action_type == "calendar.event.update":
        return _undo_calendar_update(ctx, original)
    if original.action_type == "task.update":
        return _undo_task_update(original)
    return {"success": False, "data": None, "error": f"Undo is not implemented for {original.action_type}"}


def _undo_calendar_create(ctx, original: AgentAction) -> dict[str, Any]:
    after = _result_state(original)
    event_id = original.resource_id or after.get("id")
    event = db.session.get(CalendarEvent, event_id)
    if not event:
        original.undo_status = ActionStatus.SUCCEEDED.value
        db.session.commit()
        return {"success": True, "data": {"status": "already_absent", "eventId": event_id}, "error": None}
    conflict = _state_mismatch(serialize_event(event), after)
    if conflict:
        return _undo_conflict(original, conflict)
    undo_id = f"undo_{original.id}"
    result = execute_action(
        "calendar.event.unschedule",
        "calendar.event.unschedule",
        {"event_id": event_id, "original_action_id": original.id},
        lambda: CalendarService().delete_event(ctx, event_id),
        action_id=undo_id,
        parent_action_id=original.parent_action_id,
    )
    _record_undo(original, undo_id)
    return result


def _undo_calendar_update(ctx, original: AgentAction) -> dict[str, Any]:
    before = original.before_state or {}
    after = _result_state(original)
    event_id = original.resource_id or before.get("id") or after.get("id")
    event = db.session.get(CalendarEvent, event_id)
    if not event:
        return _undo_conflict(original, "Event no longer exists")
    conflict = _state_mismatch(serialize_event(event), after)
    if conflict:
        return _undo_conflict(original, conflict)
    undo_id = f"undo_{original.id}"
    payload = _event_payload_from_state(before)
    result = execute_action(
        "calendar.event.restore",
        "calendar.event.restore",
        {"event_id": event_id, **payload, "original_action_id": original.id},
        lambda: CalendarService().update_event(ctx, event_id, payload, allow_overlap=False),
        action_id=undo_id,
        parent_action_id=original.parent_action_id,
        verify=lambda data: _state_mismatch(data, before) is None,
        before=lambda: serialize_event(event),
    )
    _record_undo(original, undo_id)
    return result


def _record_undo(original: AgentAction, undo_id: str) -> None:
    undo = db.session.get(AgentAction, undo_id)
    original.undo_action_id = undo_id
    original.undo_status = undo.status if undo else ActionStatus.UNKNOWN.value
    db.session.commit()


def _undo_conflict(original: AgentAction, message: str) -> dict[str, Any]:
    original.undo_status = "CONFLICT"
    original.after_state = {
        **(original.after_state or {}),
        "undo_error": message,
        "undo_error_class": ErrorClass.CONFLICT.value,
    }
    db.session.commit()
    return {"success": False, "data": None, "error": f"CONFLICT: {message}"}


def _undo_task_update(original: AgentAction) -> dict[str, Any]:
    before = original.before_state or {}
    after = _expected_task_after(original)
    task_id = original.resource_id or before.get("id") or after.get("id")
    task = db.session.get(Task, task_id)
    if not task:
        return _undo_conflict(original, "Task no longer exists")
    current = _serialize_task(task)
    conflict = _task_state_mismatch(current, after)
    if conflict:
        return _undo_conflict(original, conflict)
    undo_id = f"undo_{original.id}"
    result = execute_action(
        "task.update",
        "task.restore",
        {"task_id": task_id, "original_action_id": original.id, **before},
        lambda: task_tools.update_task(
            task_id,
            before.get("title"),
            before.get("description"),
            before.get("status"),
            before.get("priority"),
            before.get("estimated_hours"),
            before.get("is_daily_focus"),
            before.get("assignee_id"),
        ),
        action_id=undo_id,
        parent_action_id=original.parent_action_id,
        verify=lambda data: _task_state_mismatch(_serialize_task(db.session.get(Task, task_id)), before) is None,
        before=lambda: current,
    )
    _record_undo(original, undo_id)
    return result


def _result_state(action: AgentAction) -> dict[str, Any]:
    after = action.after_state or {}
    result = after.get("result")
    return result if isinstance(result, dict) else {}


def _event_payload_from_state(state: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "title": state.get("title"),
        "start": _parse_dt(state.get("start")),
        "end": _parse_dt(state.get("end")),
        "color": state.get("color"),
        "scope": state.get("scope"),
        "locked": state.get("locked"),
        "is_flexible": state.get("isFlexible"),
        "session_status": state.get("sessionStatus"),
    }
    return {key: value for key, value in payload.items() if value is not None}


def _parse_dt(value: str | None):
    if not value:
        return None
    return datetime.fromisoformat(value)


def _state_mismatch(current: dict[str, Any], expected: dict[str, Any]) -> str | None:
    checks = ("title", "start", "end", "taskId", "locked", "sessionStatus")
    for key in checks:
        if key in expected and current.get(key) != expected.get(key):
            return f"Current event {key} does not match the original action result"
    return None


def _serialize_task(task: Task | None) -> dict[str, Any]:
    if not task:
        return {}
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "priority": task.priority,
        "estimated_hours": task.estimated_hours,
        "is_daily_focus": task.is_daily_focus,
        "assignee_id": task.assignee_id,
    }


def _task_state_mismatch(current: dict[str, Any], expected: dict[str, Any]) -> str | None:
    if not expected:
        return "Missing task state for undo"
    for key in ("title", "description", "status", "priority", "estimated_hours", "is_daily_focus", "assignee_id"):
        if key in expected and current.get(key) != expected.get(key):
            return f"Current task {key} does not match the original action result"
    return None


def _expected_task_after(action: AgentAction) -> dict[str, Any]:
    before = dict(action.before_state or {})
    args = action.proposed_args or {}
    for source, target in (
        ("title", "title"),
        ("description", "description"),
        ("status", "status"),
        ("new_status", "status"),
        ("priority", "priority"),
        ("estimated_hours", "estimated_hours"),
        ("is_daily_focus", "is_daily_focus"),
        ("assignee_id", "assignee_id"),
    ):
        if source in args and args[source] is not None:
            before[target] = args[source]
    if not before:
        return _result_state(action)
    return before
