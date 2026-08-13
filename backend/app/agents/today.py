"""Deterministic Today / Next recommendation engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from ..calendar.models import CalendarEvent
from ..core.extensions import db
from ..projects.models import Project, TaskDependency
from ..tasks.models import Task
from .coverage import concept_key, infer_domain, normalize_label
from .execution_context import ExecutionContext
from .models import MasteryRecord
from .adaptation import ExecutionSignal, SignalType, adapt_from_signal


DONE_STATUSES = {"done", "completed"}
ACTIVE_STATUSES = {"todo", "backlog", "in-progress", "review", None, ""}
PRIORITY_WEIGHT = {"critical": 35, "high": 24, "medium": 12, "low": 4}


@dataclass
class WorkCandidate:
    task_id: str
    title: str
    project_id: str | None
    project_name: str | None
    eligibility: str
    blocked_by: list[dict[str, str]] = field(default_factory=list)
    deadline: str | None = None
    priority: str | None = None
    estimated_effort_minutes: int = 30
    schedule_fit: str = "unknown"
    mastery_reason: str | None = None
    plan_reason: str | None = None
    calendar_event_id: str | None = None
    scheduled_start: str | None = None
    scheduled_end: str | None = None
    session_status: str | None = None
    score: int = 0
    reasons: list[str] = field(default_factory=list)


def recommend_today(ctx: ExecutionContext, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    overrides = overrides or {}
    minutes_available = _override_minutes(overrides)
    excluded_terms = [normalize_label(term) for term in overrides.get("exclude_terms", [])]
    preferred_terms = [normalize_label(term) for term in overrides.get("prefer_terms", [])]

    missed_sessions = _mark_missed_sessions(ctx)
    adaptation = None
    if len(missed_sessions) >= 2:
        adaptation = adapt_from_signal(ctx, ExecutionSignal(
            type=SignalType.SESSION_MISSED,
            source="today",
            resource_id=missed_sessions[0]["id"],
            occurred_at=datetime.utcnow(),
            severity="medium",
            structured_payload={"missed_count": len(missed_sessions)},
        ))
    tasks = _workspace_tasks(ctx.workspace_id)
    blocked_map = _blocked_map([task.id for task in tasks])
    project_names = _project_names(ctx.workspace_id)
    weak_keys = _weak_mastery_keys(ctx)
    candidates: list[WorkCandidate] = []
    scheduled_task_ids: set[str] = set()
    for candidate in _scheduled_session_candidates(ctx, tasks, project_names):
        scheduled_task_ids.add(candidate.task_id)
        candidates.append(candidate)
    for task in tasks:
        if task.status in DONE_STATUSES:
            continue
        if task.id in scheduled_task_ids:
            continue
        haystack = normalize_label(f"{task.title} {task.description}")
        if excluded_terms and any(term and term in haystack for term in excluded_terms):
            continue
        blocked_by = blocked_map.get(task.id, [])
        if blocked_by:
            continue
        candidate = _candidate_for_task(task, project_names.get(task.project_id), weak_keys, minutes_available)
        if preferred_terms and any(term and term in haystack for term in preferred_terms):
            candidate.score += 18
            candidate.reasons.append("Matches your current preference.")
        candidates.append(candidate)

    candidates.sort(key=lambda item: item.score, reverse=True)
    now = candidates[0] if candidates else None
    next_items = candidates[1:4]
    later_count = max(0, len(candidates) - 4)
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "availability": {"minutes": minutes_available, "source": "override" if overrides.get("available_minutes") else "default"},
        "now": serialize_candidate(now) if now else None,
        "next": [serialize_candidate(item) for item in next_items],
        "later_count": later_count,
        "excluded_count": len(tasks) - len(candidates),
        "missed_sessions": missed_sessions,
        "adaptation": adaptation,
        "explanation": (now.reasons if now else ["No eligible unfinished work found."])[:6],
    }


def serialize_candidate(candidate: WorkCandidate | None) -> dict[str, Any] | None:
    if not candidate:
        return None
    return {
        "task_id": candidate.task_id,
        "title": candidate.title,
        "project_id": candidate.project_id,
        "project_name": candidate.project_name,
        "eligibility": candidate.eligibility,
        "blocked_by": candidate.blocked_by,
        "deadline": candidate.deadline,
        "priority": candidate.priority,
        "estimated_effort_minutes": candidate.estimated_effort_minutes,
        "schedule_fit": candidate.schedule_fit,
        "mastery_reason": candidate.mastery_reason,
        "plan_reason": candidate.plan_reason,
        "calendar_event_id": candidate.calendar_event_id,
        "scheduled_start": candidate.scheduled_start,
        "scheduled_end": candidate.scheduled_end,
        "session_status": candidate.session_status,
        "score": candidate.score,
        "reasons": candidate.reasons,
    }


def _candidate_for_task(task: Task, project_name: str | None, weak_keys: set[str], minutes_available: int) -> WorkCandidate:
    estimated = int((task.estimated_hours or 0.5) * 60)
    candidate = WorkCandidate(
        task_id=task.id,
        title=task.title or "Untitled task",
        project_id=task.project_id,
        project_name=project_name,
        eligibility="eligible",
        deadline=task.due_date.isoformat() if task.due_date else None,
        priority=task.priority or "medium",
        estimated_effort_minutes=max(15, estimated),
    )
    priority_score = PRIORITY_WEIGHT.get((task.priority or "medium").lower(), 8)
    candidate.score += priority_score
    candidate.reasons.append(f"{(task.priority or 'medium').title()} priority.")

    if task.is_daily_focus:
        candidate.score += 20
        candidate.reasons.append("Already marked as daily focus.")

    if task.due_date:
        days = (task.due_date.date() - datetime.utcnow().date()).days
        if days < 0:
            candidate.score += 34
            candidate.reasons.append("Overdue work needs attention.")
        elif days <= 1:
            candidate.score += 30
            candidate.reasons.append("Due within 24 hours.")
        elif days <= 3:
            candidate.score += 20
            candidate.reasons.append(f"Due in {days} days.")

    if candidate.estimated_effort_minutes <= minutes_available:
        candidate.score += 12
        candidate.schedule_fit = "fits_available_time"
        candidate.reasons.append(f"Fits your {minutes_available} minute window.")
    else:
        candidate.score -= 8
        candidate.schedule_fit = "too_large_for_available_time"
        candidate.reasons.append(f"Needs about {candidate.estimated_effort_minutes} minutes.")

    weak_match = _weak_match(task, weak_keys)
    if weak_match:
        candidate.score += 28
        candidate.mastery_reason = f"{weak_match} needs review."
        candidate.reasons.append(candidate.mastery_reason)

    if task.milestone_id or task.sprint_id:
        candidate.score += 6
        candidate.plan_reason = "Part of an active structured plan."
        candidate.reasons.append(candidate.plan_reason)
    return candidate


def _workspace_tasks(workspace_id: str) -> list[Task]:
    from sqlalchemy import or_
    return Task.query.filter(
        Task.workspace_id == workspace_id,
        or_(Task.status.in_([s for s in ACTIVE_STATUSES if s is not None]), Task.status.is_(None)),
    ).limit(200).all()


def _scheduled_session_candidates(
    ctx: ExecutionContext,
    tasks: list[Task],
    project_names: dict[str, str],
) -> list[WorkCandidate]:
    task_by_id = {task.id: task for task in tasks if task.status not in DONE_STATUSES}
    if not task_by_id:
        return []
    now = datetime.utcnow()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    events = CalendarEvent.query.filter(
        CalendarEvent.workspace_id == ctx.workspace_id,
        CalendarEvent.task_id.in_(task_by_id.keys()),
        CalendarEvent.start_time >= start,
        CalendarEvent.start_time < end,
        CalendarEvent.session_status == "SCHEDULED",
    ).order_by(CalendarEvent.start_time.asc()).all()
    candidates = []
    for event in events[:6]:
        task = task_by_id.get(event.task_id)
        if not task:
            continue
        active_bonus = 100 if event.start_time <= now <= event.end_time else 70
        candidate = _candidate_for_task(task, project_names.get(task.project_id), set(), 480)
        candidate.score += active_bonus
        candidate.calendar_event_id = event.id
        candidate.scheduled_start = event.start_time.isoformat() if event.start_time else None
        candidate.scheduled_end = event.end_time.isoformat() if event.end_time else None
        candidate.session_status = event.session_status
        candidate.reasons.insert(0, "Scheduled on your Ora calendar today.")
        candidates.append(candidate)
    return candidates


def _mark_missed_sessions(ctx: ExecutionContext) -> list[dict[str, Any]]:
    now = datetime.utcnow()
    events = CalendarEvent.query.filter(
        CalendarEvent.workspace_id == ctx.workspace_id,
        CalendarEvent.task_id.isnot(None),
        CalendarEvent.end_time < now,
        CalendarEvent.session_status == "SCHEDULED",
    ).limit(50).all()
    for event in events:
        event.session_status = "MISSED"
    if events:
        db.session.commit()
    return [
        {
            "id": event.id,
            "task_id": event.task_id,
            "title": event.title,
            "start": event.start_time.isoformat() if event.start_time else None,
            "end": event.end_time.isoformat() if event.end_time else None,
        }
        for event in events
    ]


def _blocked_map(task_ids: list[str]) -> dict[str, list[dict[str, str]]]:
    if not task_ids:
        return {}
    deps = TaskDependency.query.filter(TaskDependency.task_id.in_(task_ids)).all()
    blocked: dict[str, list[dict[str, str]]] = {}
    for dep in deps:
        other = db.session.get(Task, dep.depends_on_task_id)
        if other and other.status not in DONE_STATUSES:
            blocked.setdefault(dep.task_id, []).append({"id": other.id, "title": other.title or "Blocking task"})
    return blocked


def _project_names(workspace_id: str) -> dict[str, str]:
    return {project.id: project.name for project in Project.query.filter_by(workspace_id=workspace_id).all()}


def _weak_mastery_keys(ctx: ExecutionContext) -> set[str]:
    return {
        record.concept_key
        for record in MasteryRecord.query.filter_by(workspace_id=ctx.workspace_id, user_id=ctx.user_id, status="NEEDS_REVIEW").all()
    }


def _weak_match(task: Task, weak_keys: set[str]) -> str | None:
    if not weak_keys:
        return None
    domain = infer_domain(f"{task.title} {task.description}")
    title_key = concept_key(task.title, domain=domain)
    if title_key in weak_keys:
        return task.title
    text = normalize_label(f"{task.title} {task.description}")
    for key in weak_keys:
        label = key.split(".", 1)[-1].replace("_", " ")
        if label in text:
            return label.title()
    return None


def _override_minutes(overrides: dict[str, Any]) -> int:
    try:
        return max(10, min(480, int(overrides.get("available_minutes") or 60)))
    except (TypeError, ValueError):
        return 60


def today_calendar_summary(ctx: ExecutionContext) -> dict[str, Any]:
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    events = CalendarEvent.query.filter(
        CalendarEvent.workspace_id == ctx.workspace_id,
        CalendarEvent.start_time >= start,
        CalendarEvent.start_time < end,
    ).order_by(CalendarEvent.start_time.asc()).limit(20).all()
    busy_minutes = 0
    for event in events:
        if event.start_time and event.end_time:
            busy_minutes += max(0, int((event.end_time - event.start_time).total_seconds() // 60))
    return {
        "event_count": len(events),
        "busy_minutes": busy_minutes,
        "events": [
            {
                "id": event.id,
                "title": event.title,
                "start": event.start_time.isoformat() if event.start_time else None,
                "end": event.end_time.isoformat() if event.end_time else None,
                "task_id": event.task_id,
                "session_status": getattr(event, "session_status", "SCHEDULED"),
            }
            for event in events[:5]
        ],
    }
