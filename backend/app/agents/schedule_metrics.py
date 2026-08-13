"""Derived scheduling metrics from durable control-plane/calendar state."""
from __future__ import annotations

from ..calendar.models import CalendarEvent
from .execution_context import ExecutionContext
from .models import AgentAction, ScheduleProposal


def schedule_metrics(ctx: ExecutionContext) -> dict[str, int]:
    proposals = ScheduleProposal.query.filter_by(workspace_id=ctx.workspace_id).all()
    applied = [p for p in proposals if p.status in {"APPLIED", "PARTIALLY_APPLIED"}]
    run_ids = {proposal.run_id for proposal in proposals if proposal.run_id}
    sessions = CalendarEvent.query.filter(
        CalendarEvent.workspace_id == ctx.workspace_id,
        CalendarEvent.task_id.isnot(None),
    ).all()
    workspace_actions = AgentAction.query.filter(AgentAction.run_id.in_(run_ids)).all() if run_ids else []
    undos = [action for action in workspace_actions if action.action_type == "calendar.event.unschedule"]
    return {
        "schedule_proposals": len(proposals),
        "schedule_proposal_acceptance": len(applied),
        "scheduled_sessions": len(sessions),
        "scheduled_session_completion": sum(1 for event in sessions if event.session_status == "COMPLETED"),
        "missed_session_rate": sum(1 for event in sessions if event.session_status == "MISSED"),
        "reschedule_rate": sum(1 for action in workspace_actions if action.action_type == "calendar.event.update"),
        "conflict_rate": sum(1 for action in workspace_actions if (action.after_state or {}).get("error_class") == "CONFLICT"),
        "infeasible_schedule_rate": sum(1 for proposal in proposals if proposal.status == "INFEASIBLE"),
        "today_session_start_rate": sum(1 for event in sessions if event.session_status == "COMPLETED"),
        "undo_rate": len(undos),
        "undo_conflict_rate": sum(1 for action in workspace_actions if action.undo_status == "CONFLICT"),
        "manual_calendar_crud_vs_ai_scheduling": CalendarEvent.query.filter_by(workspace_id=ctx.workspace_id, is_auto_generated=False).count(),
    }
