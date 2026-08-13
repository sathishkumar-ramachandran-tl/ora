"""
Calendar business logic — shared by REST routes (app/calendar/routes.py) and MCP
(app/mcp_server.py), same {"success", "data", "error"} convention as task_tools.py.

Visibility model: scope='personal' events are only visible to their owner;
scope='workspace' events are visible to any WorkspaceMember (or the workspace owner);
scope='company' events are visible to any OrganizationMember of the workspace's org.
Recurring events (recurrence_rule set on the master row) are expanded into virtual
occurrences on read — no per-occurrence rows are persisted except when materialized by
schedule_module_milestones, which creates concrete one-off events instead.
"""
import uuid
from datetime import datetime, timedelta, time as dt_time, timezone as dt_timezone
from typing import Optional

from dateutil.rrule import rrulestr
from sqlalchemy.exc import SQLAlchemyError

from .task_tools import _ok, _fail, _get_db, _get_models


VALID_EVENT_TYPES = {"task_block", "meeting", "personal", "reminder"}
VALID_SCOPES = {"personal", "workspace", "company"}


def _ctx():
    try:
        from ..agents.execution_context import get_execution_context
        return get_execution_context(required=False)
    except Exception:
        return None


def require_calendar_event_access(ctx, event_id: str, owner_required: bool = False):
    db = _get_db()
    m = _get_models()
    event = db.session.get(m.CalendarEvent, event_id)
    if not event:
        return None, f"Event {event_id} not found"
    if ctx is not None:
        from .task_tools import require_workspace_access
        error = require_workspace_access(ctx, event.workspace_id)
        if error:
            return None, error
        if owner_required and event.owner_id != ctx.user_id:
            return None, "Unauthorized: user does not own this calendar event"
    return event, None


def _normalize_dt(value: datetime) -> datetime:
    """Store datetimes as naive UTC/local-compatible values, matching existing rows."""
    if value.tzinfo is None:
        return value
    return value.astimezone(dt_timezone.utc).replace(tzinfo=None)


def _validate_event_window(start: datetime, end: datetime) -> Optional[str]:
    if not isinstance(start, datetime) or not isinstance(end, datetime):
        return "start and end must be datetime values"
    if _normalize_dt(start) >= _normalize_dt(end):
        return "Event end must be after start"
    return None


def _event_payload(event, status: str, operation_status: str = "succeeded", verified: bool = True) -> dict:
    return {
        "id": event.id,
        "title": event.title,
        "status": status,
        "operationStatus": operation_status,
        "verified": verified,
    }


def _find_duplicate_event(m, workspace_id: str, owner_id: str, title: str, start: datetime, end: datetime,
                          task_id: Optional[str], recurrence_rule: Optional[str]):
    return m.CalendarEvent.query.filter_by(
        workspace_id=workspace_id,
        owner_id=owner_id,
        title=title.strip(),
        start_time=_normalize_dt(start),
        end_time=_normalize_dt(end),
        task_id=task_id,
        recurrence_rule=recurrence_rule,
    ).first()


def _expand_occurrences(event, window_start: datetime, window_end: datetime):
    """Yield (start, end) tuples for a (possibly recurring) event within the window."""
    duration = event.end_time - event.start_time
    if not event.recurrence_rule:
        if event.start_time < window_end and event.end_time > window_start:
            yield (event.start_time, event.end_time)
        return

    try:
        rule = rrulestr(event.recurrence_rule, dtstart=event.start_time)
    except (ValueError, TypeError):
        # Malformed rule — degrade to a single occurrence rather than raising.
        if event.start_time < window_end and event.end_time > window_start:
            yield (event.start_time, event.end_time)
        return

    for occ_start in rule.between(window_start - duration, window_end, inc=True):
        occ_end = occ_start + duration
        if occ_start < window_end and occ_end > window_start:
            yield (occ_start, occ_end)


def _visible_event_ids(m, db, workspace_id: str, user_id: str, scope_filter: Optional[str] = None):
    workspace = db.session.get(m.Workspace, workspace_id)
    is_member = m.WorkspaceMember.query.filter_by(workspace_id=workspace_id, user_id=user_id).first() is not None
    is_owner = workspace and workspace.owner_id == user_id

    org_member = False
    if workspace and workspace.organization_id:
        org_member = m.OrganizationMember.query.filter_by(
            organization_id=workspace.organization_id, user_id=user_id, status='active',
        ).first() is not None

    query = m.CalendarEvent.query.filter_by(workspace_id=workspace_id)
    if scope_filter:
        query = query.filter_by(scope=scope_filter)

    visible = []
    for event in query.all():
        if event.scope == 'personal':
            if event.owner_id == user_id or user_id in (event.attendees or []):
                visible.append(event)
        elif event.scope == 'workspace':
            if is_member or is_owner:
                visible.append(event)
        elif event.scope == 'company':
            if org_member or is_owner:
                visible.append(event)
        else:
            visible.append(event)
    return visible


def list_events(workspace_id: str, user_id: str, start: datetime, end: datetime, scope: Optional[str] = None) -> dict:
    db = _get_db()
    m = _get_models()
    ctx = _ctx()

    if ctx is not None:
        from .task_tools import require_workspace_access
        error = require_workspace_access(ctx, workspace_id)
        if error:
            return _fail(error)
        user_id = ctx.user_id

    if not db.session.get(m.Workspace, workspace_id):
        return _fail(f"Workspace {workspace_id} not found")

    events = _visible_event_ids(m, db, workspace_id, user_id, scope)
    # Only expand master rows — materialized recurrence occurrences (recurrence_parent_id set)
    # aren't themselves expanded again.
    masters = [e for e in events if not e.recurrence_parent_id]

    occurrences = []
    for event in masters:
        for occ_start, occ_end in _expand_occurrences(event, start, end):
            occurrences.append({
                "id": event.id, "title": event.title,
                "start": occ_start.isoformat(), "end": occ_end.isoformat(),
                "type": event.type, "scope": event.scope, "color": event.color,
                "taskId": event.task_id, "isAutoGenerated": event.is_auto_generated,
                "timezone": event.timezone, "recurrenceRule": event.recurrence_rule,
                "attendees": event.attendees or [],
                "isRecurringOccurrence": occ_start != event.start_time,
            })

    occurrences.sort(key=lambda e: e["start"])
    return _ok(occurrences)


def create_event(
    workspace_id: str, owner_id: str, title: str, start: datetime, end: datetime,
    event_type: str = 'personal', scope: str = 'personal', task_id: Optional[str] = None,
    color: str = 'blue', timezone: str = 'UTC', recurrence_rule: Optional[str] = None,
    attendees: Optional[list] = None, organization_id: Optional[str] = None,
) -> dict:
    db = _get_db()
    m = _get_models()
    ctx = _ctx()

    if ctx is not None:
        from .task_tools import require_workspace_access
        error = require_workspace_access(ctx, workspace_id)
        if error:
            return _fail(error)
        if owner_id != ctx.user_id:
            return _fail("Unauthorized: owner_id must match the trusted execution user")

    if not db.session.get(m.Workspace, workspace_id):
        return _fail(f"Workspace {workspace_id} not found")
    if not owner_id or not db.session.get(m.User, owner_id):
        return _fail(f"Owner {owner_id} not found")
    if not title or not title.strip():
        return _fail("Event title is required")
    window_error = _validate_event_window(start, end)
    if window_error:
        return _fail(window_error)
    if event_type not in VALID_EVENT_TYPES:
        return _fail(f"Invalid event type '{event_type}'")
    if scope not in VALID_SCOPES:
        return _fail(f"Invalid event scope '{scope}'")
    if attendees is not None and not isinstance(attendees, list):
        return _fail("attendees must be a list of user IDs")
    if task_id:
        from .task_tools import require_task_access
        _, task_error = require_task_access(ctx, task_id)
        if task_error:
            return _fail(task_error)
        task = db.session.get(m.Task, task_id)
        if not task or task.workspace_id != workspace_id:
            return _fail(f"Task {task_id} not found in workspace {workspace_id}")
    if scope == "company":
        workspace = db.session.get(m.Workspace, workspace_id)
        expected_org_id = organization_id or getattr(workspace, "organization_id", None)
        if not expected_org_id:
            return _fail("company-scope events require an organization_id or organization workspace")
        organization_id = expected_org_id
    if recurrence_rule:
        try:
            rrulestr(recurrence_rule, dtstart=_normalize_dt(start))
        except (ValueError, TypeError) as exc:
            return _fail(f"Invalid recurrence_rule: {exc}")

    duplicate = _find_duplicate_event(m, workspace_id, owner_id, title, start, end, task_id, recurrence_rule)
    if duplicate:
        return _ok(_event_payload(duplicate, "already_exists"))

    event = m.CalendarEvent(
        id=str(uuid.uuid4()), workspace_id=workspace_id, owner_id=owner_id,
        organization_id=organization_id, title=title.strip(),
        start_time=_normalize_dt(start), end_time=_normalize_dt(end),
        type=event_type, scope=scope, task_id=task_id, color=color, timezone=timezone,
        recurrence_rule=recurrence_rule, attendees=attendees or [],
    )
    try:
        db.session.add(event)
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        return _fail(f"Calendar event create failed: {exc.__class__.__name__}")

    verified_event = db.session.get(m.CalendarEvent, event.id)
    if not verified_event:
        return _fail("Calendar event create outcome is unknown; verification failed")
    return _ok(_event_payload(verified_event, "created"))


def update_event(
    event_id: str, title: Optional[str] = None, start: Optional[datetime] = None,
    end: Optional[datetime] = None, color: Optional[str] = None, scope: Optional[str] = None,
) -> dict:
    db = _get_db()
    m = _get_models()

    event, error = require_calendar_event_access(_ctx(), event_id)
    if error:
        return _fail(error)

    effective_start = _normalize_dt(start) if start is not None else event.start_time
    effective_end = _normalize_dt(end) if end is not None else event.end_time
    window_error = _validate_event_window(effective_start, effective_end)
    if window_error:
        return _fail(window_error)
    if title is not None and not title.strip():
        return _fail("Event title cannot be empty")
    if scope is not None and scope not in VALID_SCOPES:
        return _fail(f"Invalid event scope '{scope}'")

    if title is not None:
        event.title = title.strip()
    if start is not None:
        event.start_time = _normalize_dt(start)
    if end is not None:
        event.end_time = _normalize_dt(end)
    if color is not None:
        event.color = color
    if scope is not None:
        event.scope = scope

    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        return _fail(f"Calendar event update failed: {exc.__class__.__name__}")

    verified_event = db.session.get(m.CalendarEvent, event.id)
    if not verified_event:
        return _fail("Calendar event update outcome is unknown; verification failed")
    if verified_event.start_time != effective_start or verified_event.end_time != effective_end:
        return _fail("Calendar event update outcome is unknown; persisted time did not match request")
    return _ok(_event_payload(verified_event, "updated"))


def delete_event(event_id: str, delete_series: bool = False) -> dict:
    db = _get_db()
    m = _get_models()

    event, error = require_calendar_event_access(_ctx(), event_id, owner_required=True)
    if error:
        return _fail(error)

    deleted_ids = [event.id]
    if delete_series:
        root_id = event.recurrence_parent_id or event.id
        series = m.CalendarEvent.query.filter(
            (m.CalendarEvent.id == root_id) | (m.CalendarEvent.recurrence_parent_id == root_id)
        ).all()
        deleted_ids.extend(e.id for e in series)
        # Occurrences FK-reference the root via recurrence_parent_id — delete them
        # first (as a bulk query, since plain session.delete() order isn't guaranteed
        # for self-referencing FKs with no relationship() to sort by) or the root's
        # delete trips the constraint.
        m.CalendarEvent.query.filter(
            m.CalendarEvent.recurrence_parent_id == root_id
        ).delete(synchronize_session=False)
        db.session.flush()
        root = db.session.get(m.CalendarEvent, root_id)
        if root:
            db.session.delete(root)
    else:
        db.session.delete(event)

    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        return _fail(f"Calendar event delete failed: {exc.__class__.__name__}")

    unique_deleted_ids = list(set(deleted_ids))
    still_present = [eid for eid in unique_deleted_ids if db.session.get(m.CalendarEvent, eid)]
    if still_present:
        return _fail(f"Calendar event delete outcome is unknown; still present: {still_present}")
    return _ok({
        "deletedEventIds": unique_deleted_ids,
        "status": "deleted",
        "operationStatus": "succeeded",
        "verified": True,
    })


def find_availability(
    workspace_id: str, attendee_user_ids: list, duration_minutes: int,
    window_start: datetime, window_end: datetime, day_start_hour: int = 9, day_end_hour: int = 18,
    weekdays_only: bool = False,
) -> dict:
    """Scans attendees' events for open slots within working hours — the actual
    intelligence-layer tool, not just CRUD. Returns up to 10 candidate slots.
    weekdays_only=True skips Saturday/Sunday days entirely."""
    db = _get_db()
    m = _get_models()

    ctx = _ctx()
    from .task_tools import require_workspace_access
    error = require_workspace_access(ctx, workspace_id)
    if error:
        return _fail(error)

    duration = timedelta(minutes=duration_minutes)
    busy_intervals = []
    for user_id in attendee_user_ids:
        visible = _visible_event_ids(m, db, workspace_id, user_id)
        masters = [e for e in visible if not e.recurrence_parent_id]
        for event in masters:
            for occ_start, occ_end in _expand_occurrences(event, window_start, window_end):
                busy_intervals.append((occ_start, occ_end))

    busy_intervals.sort()

    slots = []
    cursor = window_start
    day = cursor
    while day.date() <= window_end.date() and len(slots) < 10:
        if weekdays_only and day.weekday() >= 5:
            day = day + timedelta(days=1)
            continue

        day_open = day.replace(hour=day_start_hour, minute=0, second=0, microsecond=0)
        day_close = day.replace(hour=day_end_hour, minute=0, second=0, microsecond=0)
        probe = max(day_open, window_start)
        day_busy = sorted(b for b in busy_intervals if b[0].date() == day.date() or b[1].date() == day.date())

        while probe + duration <= day_close and probe + duration <= window_end and len(slots) < 10:
            conflict = next((b for b in day_busy if probe < b[1] and probe + duration > b[0]), None)
            if conflict:
                probe = conflict[1]
                continue
            slots.append({"start": probe.isoformat(), "end": (probe + duration).isoformat()})
            probe = probe + duration

        day = day + timedelta(days=1)

    return _ok({"slots": slots, "attendeeCount": len(attendee_user_ids)})


def auto_schedule_tasks(
    workspace_id: str, user_id: str, task_ids: Optional[list] = None,
    day_start_hour: int = 9, day_end_hour: int = 18, weekdays_only: bool = True,
    window_end: Optional[str] = None, block_hours: Optional[float] = None,
) -> dict:
    """Real, calendar-aware auto-scheduler: places each task's estimated-hours block into
    a genuinely free slot (respects existing events, working hours, and weekday-only), one
    task at a time so later tasks see earlier ones as busy. Unlike the legacy Gemini-freeform
    optimizer, this never invents a schedule — every block comes from find_availability."""
    db = _get_db()
    m = _get_models()

    ctx = _ctx()
    from .task_tools import require_workspace_access
    error = require_workspace_access(ctx, workspace_id)
    if error:
        return _fail(error)
    if ctx is not None:
        user_id = ctx.user_id

    if not db.session.get(m.Workspace, workspace_id):
        return _fail(f"Workspace {workspace_id} not found")

    if task_ids:
        tasks = [t for t in (db.session.get(m.Task, tid) for tid in task_ids) if t]
    else:
        scheduled_task_ids = {
            e.task_id for e in m.CalendarEvent.query.filter(
                m.CalendarEvent.workspace_id == workspace_id,
                m.CalendarEvent.task_id.isnot(None),
            ).all()
        }
        tasks = [
            t for t in m.Task.query.filter_by(workspace_id=workspace_id).all()
            if t.status != 'done' and t.id not in scheduled_task_ids
        ]
        priority_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        tasks.sort(key=lambda t: (
            priority_rank.get(t.priority, 2),
            t.due_date or datetime.max,
        ))

    if not tasks:
        return _fail("No tasks to schedule")

    now = datetime.utcnow()
    if window_end:
        # window_end may arrive as a bare date ("YYYY-MM-DD"), a naive ISO datetime, or a
        # timezone-aware ISO datetime (frontend Date.toISOString()) — normalize to naive,
        # since all CalendarEvent/Task datetimes in this system are stored naive-UTC.
        window_end_dt = datetime.fromisoformat(window_end.replace('Z', '+00:00'))
        if window_end_dt.tzinfo is not None:
            window_end_dt = window_end_dt.replace(tzinfo=None)
        if window_end_dt.time() == dt_time.min:
            # Midnight means "end of that day" here, not "start of that day" — otherwise a
            # target date passed as a bare date (or as UTC midnight) would exclude the whole
            # target day from the schedulable window.
            window_end_dt = window_end_dt.replace(hour=23, minute=59, second=59)
    else:
        window_end_dt = now + timedelta(days=14)
    if window_end_dt <= now:
        return _fail("targetEndDate must be in the future")

    scheduled = []
    unscheduled = []
    for task in tasks:
        duration_minutes = int((block_hours or task.estimated_hours or 1.0) * 60)
        availability = find_availability(
            workspace_id, [user_id], duration_minutes, now, window_end_dt,
            day_start_hour=day_start_hour, day_end_hour=day_end_hour, weekdays_only=weekdays_only,
        )
        slots = availability["data"]["slots"] if availability["success"] else []
        if not slots:
            unscheduled.append({"taskId": task.id, "title": task.title})
            continue

        slot = slots[0]
        start = datetime.fromisoformat(slot["start"])
        end = datetime.fromisoformat(slot["end"])
        result = create_event(
            workspace_id, user_id, f"Focus: {task.title}", start, end,
            event_type='task_block', scope='personal', task_id=task.id, color='indigo',
        )
        if result["success"]:
            scheduled.append({
                "taskId": task.id, "title": task.title,
                "eventId": result["data"]["id"], "start": slot["start"], "end": slot["end"],
            })
        else:
            unscheduled.append({"taskId": task.id, "title": task.title})

    return _ok({
        "scheduledCount": len(scheduled), "scheduled": scheduled,
        "unscheduledCount": len(unscheduled), "unscheduled": unscheduled,
    })


def parse_schedule_constraints(instruction: str) -> dict:
    """Translates a free-text scheduling instruction (e.g. 'weekdays 9 to 5, wrap up by
    March 1') into structured auto_schedule_tasks params via a single Gemini call. Falls
    back to sane defaults if there's no API key configured or parsing fails — this must
    never hard-fail the auto-schedule flow."""
    import os as _os
    import json as _json

    defaults = {"dayStartHour": 9, "dayEndHour": 18, "weekdaysOnly": True, "targetEndDate": None}
    if not instruction or not instruction.strip():
        return defaults

    api_key = _os.environ.get('GEMINI_API_KEY') or _os.environ.get('API_KEY')
    if not api_key:
        return defaults

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        today = datetime.utcnow().date().isoformat()
        prompt = f"""Parse scheduling constraints from this instruction into structured fields.
Today's date is {today}.

Instruction: "{instruction}"

Return dayStartHour/dayEndHour as 24-hour integers (default 9/18 if unmentioned),
weekdaysOnly as a boolean (default true unless the instruction clearly wants weekend
scheduling too), and targetEndDate as an ISO date (YYYY-MM-DD) if a deadline or target
end date is mentioned, otherwise null."""

        response = client.models.generate_content(
            model='gemini-3-flash-preview',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type='application/json',
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "dayStartHour": {"type": "INTEGER"},
                        "dayEndHour": {"type": "INTEGER"},
                        "weekdaysOnly": {"type": "BOOLEAN"},
                        "targetEndDate": {"type": "STRING"},
                    },
                    "required": ["dayStartHour", "dayEndHour", "weekdaysOnly"],
                },
            ),
        )
        parsed = response.parsed if getattr(response, 'parsed', None) else _json.loads(response.text)
        return {
            "dayStartHour": int(parsed.get("dayStartHour", 9)),
            "dayEndHour": int(parsed.get("dayEndHour", 18)),
            "weekdaysOnly": bool(parsed.get("weekdaysOnly", True)),
            "targetEndDate": parsed.get("targetEndDate") or None,
        }
    except Exception:
        return defaults


def schedule_module_milestones(module_instance_id: str, workspace_id: str, user_id: str, block_hours: float = 2.0) -> dict:
    """Reads an installed module's milestones and auto-creates task_block events for
    them, using find_availability so blocks land in genuinely free time rather than
    overlapping existing commitments. The concrete Phase-1/Phase-2 integration point."""
    db = _get_db()
    m = _get_models()

    ctx = _ctx()
    from .task_tools import require_workspace_access
    error = require_workspace_access(ctx, workspace_id)
    if error:
        return _fail(error)
    if ctx is not None:
        user_id = ctx.user_id

    instance = db.session.get(m.ModuleInstance, module_instance_id)
    if not instance or instance.workspace_id != workspace_id:
        return _fail(f"Module instance {module_instance_id} not found in this workspace")

    milestones = m.Milestone.query.filter_by(project_id=instance.project_id).order_by(m.Milestone.order).all()
    if not milestones:
        return _fail("Module has no milestones to schedule")

    now = datetime.utcnow()
    created = []
    for i, milestone in enumerate(milestones):
        target_date = milestone.due_date or (now + timedelta(weeks=i + 1))
        window_start = max(now, target_date - timedelta(days=6))
        window_end = target_date + timedelta(days=1)

        availability = find_availability(
            workspace_id, [user_id], int(block_hours * 60), window_start, window_end,
        )
        slots = availability["data"]["slots"] if availability["success"] else []
        if not slots:
            continue

        slot = slots[0]
        start = datetime.fromisoformat(slot["start"])
        end = datetime.fromisoformat(slot["end"])
        result = create_event(
            workspace_id, user_id, f"Focus: {milestone.title}", start, end,
            event_type='task_block', scope='personal', color='indigo',
        )
        if result["success"]:
            created.append({"milestoneId": milestone.id, "eventId": result["data"]["id"], "start": slot["start"]})

    return _ok({"scheduledCount": len(created), "events": created})
