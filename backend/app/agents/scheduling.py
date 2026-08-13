"""Proposal-first scheduling for Ora's first-party calendar.

Plan = what. Schedule = when. Calendar = committed time state.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

from ..calendar.models import CalendarEvent
from ..calendar.service import CalendarService, TimeInterval, serialize_event
from ..core.extensions import db
from ..projects.models import TaskDependency
from ..tasks.models import Task
from ..tools.task_tools import require_project_access, require_task_access, require_workspace_access
from .action_executor import ensure_agent_run, execute_action
from .control_plane import ActionStatus, AgentRunStatus
from .execution_context import ExecutionContext, get_execution_context
from .models import AgentAction, AgentRun, MasteryRecord, ScheduleProposal


READY = "READY"
INFEASIBLE = "INFEASIBLE"
APPLYING = "APPLYING"
APPLIED = "APPLIED"
PARTIALLY_APPLIED = "PARTIALLY_APPLIED"
FAILED = "FAILED"

DONE_TASK_STATUSES = {"done", "completed"}
WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


@dataclass
class ScheduleTask:
    task: Task
    effort_minutes: int


def create_schedule_proposal(
    ctx: ExecutionContext,
    *,
    task_ids: Optional[list[str]] = None,
    project_id: Optional[str] = None,
    window_start: Optional[datetime] = None,
    window_end: Optional[datetime] = None,
    constraints: Optional[list[dict[str, Any]]] = None,
    timezone: str = "UTC",
    day_start_hour: int = 9,
    day_end_hour: int = 18,
    weekdays_only: bool = True,
    title: str | None = None,
    supersedes_id: str | None = None,
    revision_reason: str | None = None,
) -> ScheduleProposal:
    _authorize_scope(ctx, project_id, task_ids or [])
    run = ensure_agent_run(ctx)
    window_start = window_start or datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    window_end = window_end or (window_start + timedelta(days=7))
    constraints = constraints or []
    tasks = _load_tasks(ctx, task_ids, project_id)
    ordered = _dependency_order(tasks)
    scheduled, unscheduled, summary = _allocate_sessions(
        ctx,
        [ScheduleTask(task, _estimate_minutes(task)) for task in ordered],
        window_start,
        window_end,
        constraints,
        day_start_hour=day_start_hour,
        day_end_hour=day_end_hour,
        weekdays_only=weekdays_only,
        timezone=timezone,
    )
    status = READY if not unscheduled else INFEASIBLE
    proposal = ScheduleProposal(
        id=str(uuid.uuid4()),
        run_id=run.id,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        status=status,
        window_start=window_start,
        window_end=window_end,
        timezone=timezone,
        constraints=constraints,
        sessions=scheduled,
        summary={
            **summary,
            "taskCount": len(tasks),
            "sessionCount": len(scheduled),
            "unscheduled": unscheduled,
            "infeasible": bool(unscheduled),
        },
        supersedes_id=supersedes_id,
        revision_reason=revision_reason,
    )
    proposal.summary["title"] = title or "Schedule proposal"
    db.session.add(proposal)
    db.session.commit()
    return proposal


def should_create_schedule_proposal(message: str) -> bool:
    text = (message or "").lower()
    schedule_words = ("schedule", "calendar", "make time", "rebalance", "reschedule")
    planning_words = ("this week", "week", "tomorrow", "next two weeks", "study", "work session")
    direct_crud = ("delete", "remove event", "cancel event")
    return any(word in text for word in schedule_words) and any(word in text for word in planning_words) and not any(word in text for word in direct_crud)


def apply_schedule_proposal(proposal_id: str, *, approved: bool = True, fail_refs: Optional[set[str]] = None) -> dict:
    ctx = get_execution_context(required=True)
    proposal = db.session.get(ScheduleProposal, proposal_id)
    error = _validate_schedule_access(ctx, proposal)
    if error:
        return {"success": False, "data": None, "error": error}
    if proposal.status == INFEASIBLE:
        return {"success": False, "data": serialize_schedule(proposal), "error": "Schedule proposal is infeasible"}
    if not approved:
        parent = _ensure_parent_apply_action(ctx, proposal)
        parent.status = ActionStatus.WAITING_FOR_CONFIRMATION.value
        proposal.applied_action_id = parent.id
        db.session.commit()
        return {"success": False, "data": serialize_schedule(proposal), "error": "Confirmation required"}

    parent = _ensure_parent_apply_action(ctx, proposal)
    parent.status = ActionStatus.APPROVED.value
    proposal.status = APPLYING
    proposal.applied_action_id = parent.id
    db.session.commit()

    compiled = []
    successes = failures = unknown = skipped = 0
    fail_refs = fail_refs or set()
    service = CalendarService()
    for session in proposal.sessions or []:
        action_id = f"schedule_{proposal.id}_v{proposal.version}_{session['session_ref']}"
        args = _session_to_event_args(proposal, session)
        result = execute_action(
            "calendar.event.create",
            "calendar.event.create",
            args,
            lambda args=args, session=session: _create_calendar_session(ctx, service, args, session, fail_refs),
            action_id=action_id,
            parent_action_id=parent.id,
            verify=lambda data, args=args: _verify_event(data, args),
        )
        action = db.session.get(AgentAction, action_id)
        status = action.status if action else ActionStatus.UNKNOWN.value
        resource_id = action.resource_id if action else None
        if status == ActionStatus.SUCCEEDED.value:
            successes += 1
            _store_session_event_id(proposal, session["session_ref"], resource_id)
        elif status == ActionStatus.UNKNOWN.value:
            unknown += 1
        else:
            failures += 1
        compiled.append({
            "session_ref": session["session_ref"],
            "action_id": action_id,
            "status": status,
            "resource_id": resource_id,
            "error": result.get("error"),
        })

    parent.after_state = {"result": {"successes": successes, "failures": failures, "unknown": unknown, "skipped": skipped}}
    parent.status = ActionStatus.SUCCEEDED.value if failures == 0 and unknown == 0 and skipped == 0 else ActionStatus.FAILED.value
    parent.completed_at = datetime.utcnow()
    proposal.compiled_actions = compiled
    proposal.application_result = {"successes": successes, "failures": failures, "unknown": unknown, "skipped": skipped}
    proposal.status = APPLIED if failures == 0 and unknown == 0 and skipped == 0 else PARTIALLY_APPLIED
    proposal.applied_at = datetime.utcnow()

    run = db.session.get(AgentRun, parent.run_id)
    if run:
        run.status = AgentRunStatus.COMPLETED.value if proposal.status == APPLIED else AgentRunStatus.PARTIALLY_COMPLETED.value
        run.completed_at = datetime.utcnow()
    db.session.commit()
    return {"success": proposal.status == APPLIED, "data": serialize_schedule(proposal), "error": None}


def create_schedule_revision(
    ctx: ExecutionContext,
    base_proposal_id: str,
    *,
    unavailable_weekdays: Optional[list[str | int]] = None,
    fixed_event_ids: Optional[list[str]] = None,
    reason: str = "Schedule revision",
) -> ScheduleProposal:
    base = db.session.get(ScheduleProposal, base_proposal_id)
    error = _validate_schedule_access(ctx, base)
    if error:
        raise PermissionError(error)
    constraints = list(base.constraints or [])
    for weekday in unavailable_weekdays or []:
        constraints.append({"type": "unavailable_weekday", "weekday": _weekday_number(weekday)})
    for event_id in fixed_event_ids or []:
        event = db.session.get(CalendarEvent, event_id)
        if event and event.workspace_id == ctx.workspace_id:
            event.locked = True
            event.is_flexible = False
            constraints.append({"type": "fixed_event", "event_id": event.id})
    db.session.commit()
    task_ids = sorted({session["task_id"] for session in base.sessions or [] if session.get("task_id")})
    return create_schedule_proposal(
        ctx,
        task_ids=task_ids,
        window_start=base.window_start,
        window_end=base.window_end,
        constraints=constraints,
        timezone=base.timezone,
        title=f"Revision: {base.summary.get('title', 'schedule')}",
        supersedes_id=base.id,
        revision_reason=reason,
    )


def complete_calendar_session(ctx: ExecutionContext, event_id: str) -> dict:
    event, error = _require_event(ctx, event_id)
    if error:
        return {"success": False, "data": None, "error": error}
    result = CalendarService().complete_session(ctx, event_id)
    if result.get("success") and event and event.task_id:
        _record_session_effort(ctx, event)
    return result


def detect_missed_sessions(ctx: ExecutionContext, now: datetime | None = None) -> list[dict[str, Any]]:
    return CalendarService().mark_missed_sessions(ctx, now=now)


def serialize_schedule(proposal: ScheduleProposal) -> dict[str, Any]:
    return {
        "id": proposal.id,
        "runId": proposal.run_id,
        "workspaceId": proposal.workspace_id,
        "status": proposal.status,
        "version": proposal.version,
        "windowStart": proposal.window_start.isoformat(),
        "windowEnd": proposal.window_end.isoformat(),
        "timezone": proposal.timezone,
        "constraints": proposal.constraints or [],
        "sessions": proposal.sessions or [],
        "summary": proposal.summary or {},
        "compiledActions": proposal.compiled_actions or [],
        "applicationResult": proposal.application_result or {},
        "appliedActionId": proposal.applied_action_id,
        "supersedesId": proposal.supersedes_id,
        "revisionReason": proposal.revision_reason,
    }


def _allocate_sessions(
    ctx: ExecutionContext,
    tasks: list[ScheduleTask],
    window_start: datetime,
    window_end: datetime,
    constraints: list[dict[str, Any]],
    *,
    day_start_hour: int,
    day_end_hour: int,
    weekdays_only: bool,
    timezone: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    service = CalendarService()
    intervals = [
        _dict_interval(slot)
        for slot in service.availability(
            ctx, window_start, window_end,
            day_start_hour=day_start_hour, day_end_hour=day_end_hour,
            weekdays_only=weekdays_only,
        )
    ]
    unavailable = {_weekday_number(c.get("weekday")) for c in constraints if c.get("type") == "unavailable_weekday"}
    intervals = [i for i in intervals if i.start.weekday() not in unavailable]
    required = sum(task.effort_minutes for task in tasks)
    available = sum(interval.minutes for interval in intervals)
    sessions: list[dict[str, Any]] = []
    unscheduled: list[dict[str, Any]] = []
    interval_index = 0

    for item in tasks:
        remaining = item.effort_minutes
        piece = 1
        while remaining > 0 and interval_index < len(intervals):
            interval = intervals[interval_index]
            if interval.minutes < 15:
                interval_index += 1
                continue
            duration = min(remaining, min(60, interval.minutes))
            if duration < 30 and remaining > duration:
                interval_index += 1
                continue
            start = interval.start
            end = start + timedelta(minutes=duration)
            sessions.append({
                "session_ref": f"{item.task.id}-{piece}",
                "task_id": item.task.id,
                "title": item.task.title or "Work session",
                "start_at": start.isoformat(),
                "end_at": end.isoformat(),
                "duration_minutes": duration,
                "reason": "Scheduled by dependency/deadline order into verified free time.",
                "fixed": False,
                "flexible": True,
                "timezone": timezone,
            })
            remaining -= duration
            piece += 1
            interval = TimeInterval(end, interval.end)
            if interval.minutes > 0:
                intervals[interval_index] = interval
            else:
                interval_index += 1
        if remaining > 0:
            unscheduled.append({
                "task_id": item.task.id,
                "title": item.task.title,
                "missing_minutes": remaining,
                "required_minutes": item.effort_minutes,
            })
    return sessions, unscheduled, {"requiredMinutes": required, "availableMinutes": available}


def _load_tasks(ctx: ExecutionContext, task_ids: Optional[list[str]], project_id: Optional[str]) -> list[Task]:
    query = Task.query.filter(Task.workspace_id == ctx.workspace_id)
    if task_ids:
        query = query.filter(Task.id.in_(task_ids))
    if project_id:
        query = query.filter(Task.project_id == project_id)
    tasks = [task for task in query.all() if task.status not in DONE_TASK_STATUSES]
    weak_keys = {
        record.concept_key
        for record in MasteryRecord.query.filter_by(
            workspace_id=ctx.workspace_id,
            user_id=ctx.user_id,
            status="NEEDS_REVIEW",
        ).all()
    }
    priority = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(tasks, key=lambda t: (
        0 if _task_matches_weak_mastery(t, weak_keys) else 1,
        priority.get((t.priority or "medium").lower(), 2),
        t.due_date or datetime.max,
        t.title or "",
    ))


def _task_matches_weak_mastery(task: Task, weak_keys: set[str]) -> bool:
    if not weak_keys:
        return False
    text = (task.title or "").lower()
    for key in weak_keys:
        label = key.split(".", 1)[-1].replace("_", " ").lower()
        if label and label in text:
            return True
    return False


def _dependency_order(tasks: list[Task]) -> list[Task]:
    by_id = {task.id: task for task in tasks}
    deps = TaskDependency.query.filter(TaskDependency.task_id.in_(by_id)).all() if by_id else []
    depends: dict[str, set[str]] = {task.id: set() for task in tasks}
    for dep in deps:
        if dep.depends_on_task_id in by_id:
            depends.setdefault(dep.task_id, set()).add(dep.depends_on_task_id)
    ordered: list[Task] = []
    while depends:
        ready = [task_id for task_id, blockers in depends.items() if not blockers]
        if not ready:
            ordered.extend(by_id[task_id] for task_id in depends)
            break
        for task_id in sorted(ready, key=lambda tid: tasks.index(by_id[tid])):
            ordered.append(by_id[task_id])
            depends.pop(task_id, None)
            for blockers in depends.values():
                blockers.discard(task_id)
    return ordered


def _estimate_minutes(task: Task) -> int:
    try:
        minutes = int(float(task.estimated_hours or 1.0) * 60)
    except (TypeError, ValueError):
        minutes = 60
    return max(15, min(24 * 60, minutes))


def _authorize_scope(ctx: ExecutionContext, project_id: str | None, task_ids: list[str]) -> None:
    error = require_workspace_access(ctx, ctx.workspace_id)
    if error:
        raise PermissionError(error)
    if project_id:
        _, error = require_project_access(ctx, project_id)
        if error:
            raise PermissionError(error)
    for task_id in task_ids:
        _, error = require_task_access(ctx, task_id)
        if error:
            raise PermissionError(error)


def _validate_schedule_access(ctx: ExecutionContext, proposal: Optional[ScheduleProposal]) -> Optional[str]:
    if not proposal:
        return "ScheduleProposal not found"
    if proposal.workspace_id != ctx.workspace_id:
        return "Unauthorized: schedule is outside the trusted workspace"
    return require_workspace_access(ctx, proposal.workspace_id)


def _ensure_parent_apply_action(ctx: ExecutionContext, proposal: ScheduleProposal) -> AgentAction:
    run = ensure_agent_run(ctx)
    action_id = f"schedule_apply_{proposal.id}_v{proposal.version}"
    action = db.session.get(AgentAction, action_id)
    if action:
        return action
    action = AgentAction(
        id=action_id,
        run_id=run.id,
        action_type="schedule.apply",
        resource_type="schedule",
        resource_id=proposal.id,
        status=ActionStatus.PROPOSED.value,
        risk_level="HIGH",
        confirmation_required=True,
        idempotency_key=f"act_{action_id}",
        proposed_args={"schedule_proposal_id": proposal.id, "version": proposal.version},
    )
    db.session.add(action)
    db.session.commit()
    return action


def _session_to_event_args(proposal: ScheduleProposal, session: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": session["title"],
        "start": datetime.fromisoformat(session["start_at"]),
        "end": datetime.fromisoformat(session["end_at"]),
        "event_type": "task_block",
        "scope": "personal",
        "task_id": session["task_id"],
        "color": "indigo",
        "timezone": proposal.timezone,
        "is_flexible": bool(session.get("flexible", True)),
        "locked": bool(session.get("fixed", False)),
        "session_status": "SCHEDULED",
    }


def _create_calendar_session(
    ctx: ExecutionContext,
    service: CalendarService,
    args: dict[str, Any],
    session: dict[str, Any],
    fail_refs: set[str],
) -> dict:
    if session["session_ref"] in fail_refs:
        return {"success": False, "data": None, "error": "Validation error: forced schedule failure"}
    return service.create_event(ctx, args)


def _verify_event(data: dict[str, Any], args: dict[str, Any]) -> bool:
    event_id = data.get("id")
    event = db.session.get(CalendarEvent, event_id)
    if not event:
        return False
    return (
        event.start_time == args["start"]
        and event.end_time == args["end"]
        and event.task_id == args["task_id"]
    )


def _store_session_event_id(proposal: ScheduleProposal, session_ref: str, event_id: str | None) -> None:
    sessions = list(proposal.sessions or [])
    for item in sessions:
        if item.get("session_ref") == session_ref:
            item["event_id"] = event_id
    proposal.sessions = sessions


def _dict_interval(slot: dict[str, Any]) -> TimeInterval:
    return TimeInterval(datetime.fromisoformat(slot["start"]), datetime.fromisoformat(slot["end"]))


def _weekday_number(value: Any) -> int:
    if isinstance(value, int):
        return value
    text = str(value or "").strip().lower()
    if text.isdigit():
        return int(text)
    return WEEKDAYS.get(text, 0)


def _require_event(ctx: ExecutionContext, event_id: str) -> tuple[CalendarEvent | None, str | None]:
    event = db.session.get(CalendarEvent, event_id)
    if not event or event.workspace_id != ctx.workspace_id:
        return None, f"Event {event_id} not found"
    return event, None


def _record_session_effort(ctx: ExecutionContext, event: CalendarEvent) -> None:
    from ..workspaces.models import Workspace
    workspace = db.session.get(Workspace, ctx.workspace_id)
    if not workspace:
        return
    settings = dict(workspace.settings or {})
    execution = dict(settings.get("execution_preferences") or {})
    history = list(execution.get("session_history") or [])[-24:]
    minutes = int((event.end_time - event.start_time).total_seconds() // 60) if event.start_time and event.end_time else 0
    history.append({
        "task_id": event.task_id,
        "event_id": event.id,
        "minutes": minutes,
        "completed_at": datetime.utcnow().isoformat(),
        "time_of_day": event.start_time.hour if event.start_time else None,
    })
    execution["session_history"] = history
    if history:
        execution["preferred_session_minutes"] = round(sum(item["minutes"] for item in history) / len(history))
    settings["execution_preferences"] = execution
    workspace.settings = settings
    db.session.commit()
