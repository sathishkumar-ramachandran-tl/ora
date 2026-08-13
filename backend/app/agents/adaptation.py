"""Execution feedback → deterministic adaptation decisions.

This is a service-layer control loop, not an event bus. Evidence becomes a normalized
signal, the application classifies impact, then Today/Schedule/Plan can react.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from ..calendar.models import CalendarEvent
from ..core.extensions import db
from ..projects.models import TaskDependency
from ..tasks.models import Task
from .coverage import normalize_label
from .execution_context import ExecutionContext
from .models import MasteryRecord, ScheduleProposal
from .scheduling import create_schedule_proposal, serialize_schedule


class SignalType(str, Enum):
    SESSION_MISSED = "SESSION_MISSED"
    SESSION_COMPLETED = "SESSION_COMPLETED"
    ASSESSMENT_FAILED = "ASSESSMENT_FAILED"
    ASSESSMENT_PASSED = "ASSESSMENT_PASSED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_BLOCKED = "TASK_BLOCKED"
    DEADLINE_CHANGED = "DEADLINE_CHANGED"
    AVAILABILITY_CHANGED = "AVAILABILITY_CHANGED"


class ImpactDecision(str, Enum):
    NO_CHANGE = "NO_CHANGE"
    TODAY_ADJUSTMENT = "TODAY_ADJUSTMENT"
    SCHEDULE_REVISION = "SCHEDULE_REVISION"
    PLAN_REVISION = "PLAN_REVISION"


@dataclass(frozen=True)
class ExecutionSignal:
    type: SignalType
    source: str
    resource_id: str | None
    occurred_at: datetime
    severity: str
    structured_payload: dict[str, Any]


def signal_from_mastery(mastery: MasteryRecord) -> ExecutionSignal:
    signal_type = SignalType.ASSESSMENT_FAILED if mastery.status == "NEEDS_REVIEW" else SignalType.ASSESSMENT_PASSED
    return ExecutionSignal(
        type=signal_type,
        source=mastery.evidence_type or "assessment",
        resource_id=mastery.evidence_id,
        occurred_at=mastery.assessed_at or datetime.utcnow(),
        severity="high" if mastery.status == "NEEDS_REVIEW" else "low",
        structured_payload={"concept_key": mastery.concept_key, "mastery_status": mastery.status},
    )


def evaluate_signal(ctx: ExecutionContext, signal: ExecutionSignal) -> dict[str, Any]:
    if signal.type == SignalType.ASSESSMENT_FAILED:
        weak_count = MasteryRecord.query.filter_by(
            workspace_id=ctx.workspace_id,
            user_id=ctx.user_id,
            status="NEEDS_REVIEW",
        ).count()
        decision = ImpactDecision.PLAN_REVISION if weak_count >= 3 else ImpactDecision.SCHEDULE_REVISION
        return _decision(signal, decision, "Mastery evidence indicates prerequisite risk.")
    if signal.type == SignalType.SESSION_MISSED:
        missed = CalendarEvent.query.filter_by(
            workspace_id=ctx.workspace_id,
            session_status="MISSED",
        ).count()
        decision = ImpactDecision.SCHEDULE_REVISION if missed >= 2 else ImpactDecision.TODAY_ADJUSTMENT
        return _decision(signal, decision, "Missed scheduled execution creates local schedule risk.")
    if signal.type == SignalType.SESSION_COMPLETED:
        return _decision(signal, ImpactDecision.TODAY_ADJUSTMENT, "Completed session may free or pull forward work.")
    return _decision(signal, ImpactDecision.NO_CHANGE, "Signal recorded; no deterministic adaptation needed.")


def adapt_from_signal(ctx: ExecutionContext, signal: ExecutionSignal) -> dict[str, Any]:
    decision = evaluate_signal(ctx, signal)
    if decision["impact"] == ImpactDecision.SCHEDULE_REVISION.value:
        revision = propose_adaptive_schedule_revision(ctx, signal)
        if revision:
            decision["schedule_revision"] = serialize_schedule(revision)
    return decision


def propose_adaptive_schedule_revision(ctx: ExecutionContext, signal: ExecutionSignal) -> ScheduleProposal | None:
    base = _latest_schedule(ctx)
    if not base:
        return None
    reason = _revision_reason(signal)
    existing = ScheduleProposal.query.filter_by(
        workspace_id=ctx.workspace_id,
        supersedes_id=base.id,
        revision_reason=reason,
        status="READY",
    ).order_by(ScheduleProposal.created_at.desc()).first()
    if existing:
        return existing
    fixed_event_ids = _fixed_event_ids(ctx, base.window_start, base.window_end)
    task_ids = _unfinished_scheduled_task_ids(base)
    constraints = list(base.constraints or [])
    operations: list[dict[str, Any]] = []

    if signal.type == SignalType.ASSESSMENT_FAILED:
        concept_key = signal.structured_payload.get("concept_key")
        remediation = _get_or_create_remediation_task(ctx, concept_key)
        if remediation:
            task_ids = [remediation.id, *[tid for tid in task_ids if tid != remediation.id]]
            _copy_prerequisite_dependents_to_remediation(ctx, concept_key, remediation.id)
            operations.append({
                "op": "ADD",
                "target": remediation.title,
                "reason": "Assessment evidence marked this concept as needing review.",
                "evidence_id": signal.resource_id,
            })

    if signal.type == SignalType.SESSION_MISSED:
        operations.append({
            "op": "MOVE",
            "target": "missed flexible sessions",
            "reason": "One or more scheduled sessions were missed.",
            "evidence_id": signal.resource_id,
        })

    for event_id in fixed_event_ids:
        constraints.append({"type": "fixed_event", "event_id": event_id})
        operations.append({"op": "KEEP", "target": event_id, "reason": "Locked calendar event remains fixed."})

    revision = create_schedule_proposal(
        ctx,
        task_ids=task_ids,
        window_start=max(datetime.utcnow().replace(minute=0, second=0, microsecond=0), base.window_start),
        window_end=base.window_end,
        constraints=constraints,
        timezone=base.timezone,
        title="Adaptive schedule update",
        supersedes_id=base.id,
        revision_reason=reason,
    )
    revision.summary = {
        **(revision.summary or {}),
        "adaptation": {
            "signal": signal.type.value,
            "impact": ImpactDecision.SCHEDULE_REVISION.value,
            "why": _revision_reason(signal),
            "operations": operations,
            "fixedEventIds": fixed_event_ids,
        },
    }
    db.session.commit()
    return revision


def plan_health(ctx: ExecutionContext) -> dict[str, Any]:
    tasks = Task.query.filter_by(workspace_id=ctx.workspace_id).all()
    unfinished = [task for task in tasks if task.status not in {"done", "completed"}]
    overdue = [task for task in unfinished if task.due_date and task.due_date < datetime.utcnow()]
    weak = MasteryRecord.query.filter_by(workspace_id=ctx.workspace_id, user_id=ctx.user_id, status="NEEDS_REVIEW").count()
    capacity = _capacity_risk(ctx, unfinished)
    missed = CalendarEvent.query.filter_by(workspace_id=ctx.workspace_id, session_status="MISSED").count()

    status = "HEALTHY"
    reasons: list[str] = []
    if capacity["at_risk"]:
        status = "REVISION_RECOMMENDED"
        reasons.append(capacity["message"])
    elif len(overdue) >= 3 or weak >= 2 or missed >= 2:
        status = "AT_RISK"
    if overdue:
        reasons.append(f"{len(overdue)} overdue task{'' if len(overdue) == 1 else 's'}.")
    if weak:
        reasons.append(f"{weak} concept{'' if weak == 1 else 's'} need review.")
    if missed:
        reasons.append(f"{missed} missed session{'' if missed == 1 else 's'}.")
    if not reasons:
        reasons.append("No major adaptation signals detected.")
    return {"status": status, "reasons": reasons, "capacity": capacity}


def execution_signal_audit(ctx: ExecutionContext) -> dict[str, Any]:
    weak = MasteryRecord.query.filter_by(workspace_id=ctx.workspace_id, user_id=ctx.user_id, status="NEEDS_REVIEW").count()
    missed = CalendarEvent.query.filter_by(workspace_id=ctx.workspace_id, session_status="MISSED").count()
    completed_sessions = CalendarEvent.query.filter_by(workspace_id=ctx.workspace_id, session_status="COMPLETED").count()
    done_tasks = Task.query.filter(Task.workspace_id == ctx.workspace_id, Task.status.in_(["done", "completed"])).count()
    return {
        "session_missed": {"count": missed, "affects": ["Today", "ScheduleProposal"]},
        "session_completed": {"count": completed_sessions, "affects": ["Today", "effort evidence"]},
        "assessment_failed": {"count": weak, "affects": ["Mastery", "Today", "ScheduleProposal", "Plan health"]},
        "task_completed": {"count": done_tasks, "affects": ["Today", "progress"]},
        "deadline_changed": {"count": 0, "affects": ["Plan health", "ScheduleProposal"], "gap": "No first-class deadline-change signal yet."},
        "availability_changed": {"count": 0, "affects": ["ScheduleProposal"], "gap": "Only explicit schedule revision constraints are modeled today."},
    }


def retrieval_benchmark(ctx: ExecutionContext) -> dict[str, Any]:
    from ..calendar.models import CalendarEvent
    from .models import CompetencyEvidence, PlanProposal

    queries = ["networking", "CIDR", "my failed assessment", "advanced plan", "Friday exam"]
    results = []
    for query in queries:
        needle = normalize_label(query.replace("my ", "").replace("failed ", ""))
        hits: list[dict[str, str]] = []
        for task in Task.query.filter_by(workspace_id=ctx.workspace_id).limit(200).all():
            if needle in normalize_label(f"{task.title} {task.description}"):
                hits.append({"type": "task", "id": task.id, "title": task.title})
        for plan in PlanProposal.query.filter_by(workspace_id=ctx.workspace_id).limit(50).all():
            if needle in normalize_label(f"{plan.title} {plan.goal}"):
                hits.append({"type": "plan", "id": plan.id, "title": plan.title})
        for event in CalendarEvent.query.filter_by(workspace_id=ctx.workspace_id).limit(100).all():
            if needle in normalize_label(f"{event.title} {event.start_time:%A}" if event.start_time else event.title):
                hits.append({"type": "calendar_event", "id": event.id, "title": event.title})
        for evidence in CompetencyEvidence.query.filter_by(workspace_id=ctx.workspace_id).limit(100).all():
            text = normalize_label(f"{evidence.evidence_type} {evidence.result}")
            if "assessment" in needle and "assessment" in text:
                hits.append({"type": "competency_evidence", "id": evidence.id, "title": evidence.evidence_type})
        results.append({
            "query": query,
            "hit_count": len(hits),
            "sample": hits[:5],
            "vector_retrieval_justified": False if hits else "review_needed",
        })
    return {"results": results, "decision": "Do not add vector retrieval yet; structured recall covers the current benchmark except empty-workspace cases."}


def _decision(signal: ExecutionSignal, impact: ImpactDecision, rationale: str) -> dict[str, Any]:
    return {
        "signal": {
            "type": signal.type.value,
            "source": signal.source,
            "resource_id": signal.resource_id,
            "severity": signal.severity,
            "payload": signal.structured_payload,
        },
        "impact": impact.value,
        "rationale": rationale,
    }


def _latest_schedule(ctx: ExecutionContext) -> ScheduleProposal | None:
    return ScheduleProposal.query.filter(
        ScheduleProposal.workspace_id == ctx.workspace_id,
        ScheduleProposal.status.in_(["APPLIED", "PARTIALLY_APPLIED", "READY"]),
    ).order_by(ScheduleProposal.created_at.desc()).first()


def _unfinished_scheduled_task_ids(proposal: ScheduleProposal) -> list[str]:
    ids = []
    for session in proposal.sessions or []:
        task_id = session.get("task_id")
        task = db.session.get(Task, task_id) if task_id else None
        if task and task.status not in {"done", "completed"} and task.id not in ids:
            ids.append(task.id)
    return ids


def _fixed_event_ids(ctx: ExecutionContext, start: datetime, end: datetime) -> list[str]:
    events = CalendarEvent.query.filter(
        CalendarEvent.workspace_id == ctx.workspace_id,
        CalendarEvent.start_time < end,
        CalendarEvent.end_time > start,
        CalendarEvent.locked.is_(True),
    ).all()
    return [event.id for event in events]


def _get_or_create_remediation_task(ctx: ExecutionContext, concept_key: str | None) -> Task | None:
    if not concept_key:
        return None
    label = f"remediation:{concept_key}"
    existing = Task.query.filter(
        Task.workspace_id == ctx.workspace_id,
        Task.labels.contains([label]),
        Task.status.notin_(["done", "completed"]),
    ).first()
    if existing:
        return existing

    title = _concept_title(concept_key)
    project_id = _project_for_concept(ctx, title)
    task = Task(
        id=str(uuid.uuid4()),
        workspace_id=ctx.workspace_id,
        project_id=project_id,
        title=f"{title} Review",
        description="Adaptive remediation generated from mastery evidence.",
        status="todo",
        priority="high",
        estimated_hours=0.5,
        labels=[label, "adaptive-remediation"],
        resources=[],
    )
    db.session.add(task)
    db.session.commit()
    return task


def _project_for_concept(ctx: ExecutionContext, title: str) -> str | None:
    task = Task.query.filter(
        Task.workspace_id == ctx.workspace_id,
        Task.title.ilike(f"%{title.split()[0]}%"),
    ).first()
    return task.project_id if task else ctx.scope_project_id


def _copy_prerequisite_dependents_to_remediation(ctx: ExecutionContext, concept_key: str | None, remediation_task_id: str) -> None:
    if not concept_key:
        return
    title = _concept_title(concept_key)
    prereq_tasks = Task.query.filter(Task.workspace_id == ctx.workspace_id, Task.title.ilike(f"%{title}%")).all()
    for prereq in prereq_tasks:
        deps = TaskDependency.query.filter_by(depends_on_task_id=prereq.id).all()
        for dep in deps:
            if dep.task_id == remediation_task_id:
                continue
            exists = TaskDependency.query.filter_by(
                task_id=dep.task_id,
                depends_on_task_id=remediation_task_id,
                type="blocks",
            ).first()
            if not exists:
                db.session.add(TaskDependency(
                    task_id=dep.task_id,
                    depends_on_task_id=remediation_task_id,
                    type="blocks",
                ))
    db.session.commit()


def _concept_title(concept_key: str) -> str:
    return concept_key.split(".", 1)[-1].replace("_", " ").title()


def _revision_reason(signal: ExecutionSignal) -> str:
    if signal.type == SignalType.ASSESSMENT_FAILED:
        concept = _concept_title(str(signal.structured_payload.get("concept_key", "prerequisite")))
        return f"{concept} needs review before dependent work continues."
    if signal.type == SignalType.SESSION_MISSED:
        return "Missed sessions require a local schedule recovery."
    return "Execution signal requires a local schedule update."


def _capacity_risk(ctx: ExecutionContext, unfinished: list[Task]) -> dict[str, Any]:
    deadline_tasks = [task for task in unfinished if task.due_date]
    if not deadline_tasks:
        return {"at_risk": False, "remainingMinutes": 0, "availableMinutes": None, "message": "No dated capacity risk."}
    deadline = min(task.due_date for task in deadline_tasks)
    remaining = sum(int((task.estimated_hours or 1) * 60) for task in unfinished if not task.due_date or task.due_date <= deadline)
    from ..calendar.service import CalendarService
    available = sum(slot["durationMinutes"] for slot in CalendarService().availability(
        ctx,
        datetime.utcnow(),
        deadline,
        day_start_hour=9,
        day_end_hour=18,
        weekdays_only=True,
    ))
    at_risk = remaining > available
    return {
        "at_risk": at_risk,
        "remainingMinutes": remaining,
        "availableMinutes": available,
        "deadline": deadline.isoformat(),
        "message": f"{remaining - available} additional minutes are required before the nearest deadline." if at_risk else "Remaining dated work fits available capacity.",
    }
