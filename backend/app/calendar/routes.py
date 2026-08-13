import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..core.extensions import db
from ..core.authz import user_can_access_workspace
from ..tools import calendar_tools
from ..agents.execution_context import ExecutionContext, execution_context
from ..agents.scheduling import (
    apply_schedule_proposal,
    complete_calendar_session,
    create_schedule_proposal,
    create_schedule_revision,
    serialize_schedule,
)
from .service import CalendarService
from .models import CalendarEvent

calendar_bp = Blueprint('calendar', __name__)


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace('Z', '+00:00')).replace(tzinfo=None)


def _ctx(workspace_id: str) -> ExecutionContext:
    return ExecutionContext(
        request_id=str(uuid.uuid4()),
        user_id=get_jwt_identity(),
        workspace_id=workspace_id,
        run_id=str(uuid.uuid4()),
    )


@calendar_bp.route('/workspaces/<ws_id>/events', methods=['GET'])
@jwt_required()
def get_events(ws_id):
    current_user_id = get_jwt_identity()
    if not user_can_access_workspace(current_user_id, ws_id):
        return jsonify({"error": "Forbidden"}), 403

    start_str = request.args.get('start')
    end_str = request.args.get('end')
    scope = request.args.get('scope')
    start = _parse_dt(start_str) if start_str else datetime.utcnow()
    end = _parse_dt(end_str) if end_str else datetime.utcnow()

    result = calendar_tools.list_events(ws_id, current_user_id, start, end, scope=scope)
    if not result["success"]:
        return jsonify({"error": result["error"]}), 404
    return jsonify(result["data"])


@calendar_bp.route('/workspaces/<ws_id>/events', methods=['POST'])
@jwt_required()
def create_event(ws_id):
    current_user_id = get_jwt_identity()
    if not user_can_access_workspace(current_user_id, ws_id):
        return jsonify({"error": "Forbidden"}), 403
    data = request.json or {}

    if not data.get('title') or not data.get('start') or not data.get('end'):
        return jsonify({"error": "title, start, and end are required"}), 400

    ctx = _ctx(ws_id)
    payload = {
        "title": data['title'],
        "start": _parse_dt(data['start']),
        "end": _parse_dt(data['end']),
        "event_type": data.get('type', 'personal'),
        "scope": data.get('scope', 'personal'),
        "task_id": data.get('taskId'),
        "color": data.get('color', 'blue'),
        "timezone": data.get('timezone', 'UTC'),
        "recurrence_rule": data.get('recurrenceRule'),
        "attendees": data.get('attendees'),
        "organization_id": data.get('organizationId'),
        "is_flexible": data.get('isFlexible', data.get('is_flexible', True)),
        "locked": data.get('locked', False),
        "session_status": data.get('sessionStatus', 'SCHEDULED'),
    }
    with execution_context(ctx):
        result = CalendarService().create_event(ctx, payload, allow_overlap=bool(data.get('allowOverlap', False)))
    if not result["success"]:
        status = 409 if "CONFLICT" in (result["error"] or "") else 400
        return jsonify({"error": result["error"], "data": result.get("data")}), status
    return jsonify(result["data"]), 201


@calendar_bp.route('/events/<event_id>', methods=['PATCH'])
@jwt_required()
def update_event(event_id):
    current_user_id = get_jwt_identity()
    event = db.session.get(CalendarEvent, event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404
    if not user_can_access_workspace(current_user_id, event.workspace_id):
        return jsonify({"error": "Forbidden"}), 403

    data = request.json or {}
    ctx = _ctx(event.workspace_id)
    payload = {
        "title": data.get('title'),
        "start": _parse_dt(data['start']) if data.get('start') else None,
        "end": _parse_dt(data['end']) if data.get('end') else None,
        "color": data.get('color'),
        "scope": data.get('scope'),
        "event_type": data.get('type'),
        "is_flexible": data.get('isFlexible', data.get('is_flexible')),
        "locked": data.get('locked'),
        "session_status": data.get('sessionStatus'),
    }
    payload = {key: value for key, value in payload.items() if value is not None}
    with execution_context(ctx):
        result = CalendarService().update_event(ctx, event_id, payload, allow_overlap=bool(data.get('allowOverlap', False)))
    if not result["success"]:
        status = 409 if "CONFLICT" in (result["error"] or "") else 400
        return jsonify({"error": result["error"], "data": result.get("data")}), status
    return jsonify(result["data"])


@calendar_bp.route('/events/<event_id>', methods=['DELETE'])
@jwt_required()
def delete_event(event_id):
    current_user_id = get_jwt_identity()
    event = db.session.get(CalendarEvent, event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404
    if event.owner_id != current_user_id:
        return jsonify({"error": "Unauthorized"}), 403

    delete_series = (request.args.get('deleteSeries') or '').lower() in ('1', 'true')
    result = calendar_tools.delete_event(event_id, delete_series=delete_series)
    if not result["success"]:
        return jsonify({"error": result["error"]}), 400
    return jsonify(result["data"])


@calendar_bp.route('/workspaces/<ws_id>/availability', methods=['POST'])
@jwt_required()
def find_availability(ws_id):
    current_user_id = get_jwt_identity()
    if not user_can_access_workspace(current_user_id, ws_id):
        return jsonify({"error": "Forbidden"}), 403

    data = request.json or {}
    attendee_ids = data.get('attendeeUserIds') or [current_user_id]
    duration_minutes = data.get('durationMinutes', 60)
    if not data.get('windowStart') or not data.get('windowEnd'):
        return jsonify({"error": "windowStart and windowEnd are required"}), 400

    result = calendar_tools.find_availability(
        ws_id, attendee_ids, duration_minutes,
        _parse_dt(data['windowStart']), _parse_dt(data['windowEnd']),
        day_start_hour=data.get('dayStartHour', 9), day_end_hour=data.get('dayEndHour', 18),
    )
    if not result["success"]:
        return jsonify({"error": result["error"]}), 400
    return jsonify(result["data"])


@calendar_bp.route('/workspaces/<ws_id>/auto-schedule', methods=['POST'])
@jwt_required()
def auto_schedule(ws_id):
    """Real, calendar-aware auto-scheduling (replaces the old freeform-Gemini
    /agents/optimize-schedule path). Accepts either explicit constraint fields or a
    free-text `instruction` that gets parsed into those same fields first."""
    current_user_id = get_jwt_identity()
    if not user_can_access_workspace(current_user_id, ws_id):
        return jsonify({"error": "Forbidden"}), 403

    data = request.json or {}
    constraints = {
        "dayStartHour": data.get('dayStartHour'),
        "dayEndHour": data.get('dayEndHour'),
        "weekdaysOnly": data.get('weekdaysOnly'),
        "targetEndDate": data.get('targetEndDate'),
    }
    if data.get('instruction') and all(v is None for v in constraints.values()):
        constraints = calendar_tools.parse_schedule_constraints(data['instruction'])

    result = calendar_tools.auto_schedule_tasks(
        ws_id, current_user_id,
        task_ids=data.get('taskIds'),
        day_start_hour=constraints.get('dayStartHour') if constraints.get('dayStartHour') is not None else 9,
        day_end_hour=constraints.get('dayEndHour') if constraints.get('dayEndHour') is not None else 18,
        weekdays_only=constraints.get('weekdaysOnly') if constraints.get('weekdaysOnly') is not None else True,
        window_end=constraints.get('targetEndDate'),
        block_hours=data.get('blockHours'),
    )
    if not result["success"]:
        return jsonify({"error": result["error"]}), 400
    return jsonify(result["data"])


@calendar_bp.route('/workspaces/<ws_id>/schedule-proposals', methods=['POST'])
@jwt_required()
def propose_schedule(ws_id):
    current_user_id = get_jwt_identity()
    if not user_can_access_workspace(current_user_id, ws_id):
        return jsonify({"error": "Forbidden"}), 403
    data = request.json or {}
    ctx = _ctx(ws_id)
    with execution_context(ctx):
        proposal = create_schedule_proposal(
            ctx,
            task_ids=data.get('taskIds') or data.get('task_ids'),
            project_id=data.get('projectId') or data.get('project_id'),
            window_start=_parse_dt(data['windowStart']) if data.get('windowStart') else None,
            window_end=_parse_dt(data['windowEnd']) if data.get('windowEnd') else None,
            constraints=data.get('constraints') or [],
            timezone=data.get('timezone', 'UTC'),
            day_start_hour=int(data.get('dayStartHour', 9)),
            day_end_hour=int(data.get('dayEndHour', 18)),
            weekdays_only=bool(data.get('weekdaysOnly', True)),
            title=data.get('title'),
        )
    return jsonify(serialize_schedule(proposal)), 201


@calendar_bp.route('/schedule-proposals/<proposal_id>/apply', methods=['POST'])
@jwt_required()
def apply_schedule(proposal_id):
    from ..agents.models import ScheduleProposal
    proposal = db.session.get(ScheduleProposal, proposal_id)
    if not proposal:
        return jsonify({"error": "ScheduleProposal not found"}), 404
    if not user_can_access_workspace(get_jwt_identity(), proposal.workspace_id):
        return jsonify({"error": "Forbidden"}), 403
    data = request.json or {}
    ctx = _ctx(proposal.workspace_id)
    with execution_context(ctx):
        result = apply_schedule_proposal(proposal_id, approved=bool(data.get('approved', True)))
    status = 200 if result["data"] else 400
    return jsonify(result["data"] if result["data"] else {"error": result["error"]}), status


@calendar_bp.route('/schedule-proposals/<proposal_id>/revise', methods=['POST'])
@jwt_required()
def revise_schedule(proposal_id):
    from ..agents.models import ScheduleProposal
    base = db.session.get(ScheduleProposal, proposal_id)
    if not base:
        return jsonify({"error": "ScheduleProposal not found"}), 404
    if not user_can_access_workspace(get_jwt_identity(), base.workspace_id):
        return jsonify({"error": "Forbidden"}), 403
    data = request.json or {}
    ctx = _ctx(base.workspace_id)
    with execution_context(ctx):
        proposal = create_schedule_revision(
            ctx,
            proposal_id,
            unavailable_weekdays=data.get('unavailableWeekdays') or data.get('unavailable_weekdays') or [],
            fixed_event_ids=data.get('fixedEventIds') or data.get('fixed_event_ids') or [],
            reason=data.get('reason', 'Schedule revision'),
        )
    return jsonify(serialize_schedule(proposal)), 201


@calendar_bp.route('/events/<event_id>/complete-session', methods=['POST'])
@jwt_required()
def complete_session(event_id):
    event = db.session.get(CalendarEvent, event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404
    if not user_can_access_workspace(get_jwt_identity(), event.workspace_id):
        return jsonify({"error": "Forbidden"}), 403
    ctx = _ctx(event.workspace_id)
    with execution_context(ctx):
        result = complete_calendar_session(ctx, event_id)
    return jsonify(result["data"] if result["success"] else {"error": result["error"]}), 200 if result["success"] else 400


@calendar_bp.route('/workspaces/<ws_id>/modules/<module_instance_id>/schedule', methods=['POST'])
@jwt_required()
def schedule_module_milestones(ws_id, module_instance_id):
    current_user_id = get_jwt_identity()
    if not user_can_access_workspace(current_user_id, ws_id):
        return jsonify({"error": "Forbidden"}), 403

    data = request.json or {}
    result = calendar_tools.schedule_module_milestones(
        module_instance_id, ws_id, current_user_id, block_hours=data.get('blockHours', 2.0),
    )
    if not result["success"]:
        return jsonify({"error": result["error"]}), 400
    return jsonify(result["data"])
