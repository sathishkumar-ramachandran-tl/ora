"""First-party calendar service and provider boundary.

The agent/scheduler talks to CalendarService. Today it is backed by the Ora DB
provider; future Google Calendar support should plug in below this interface.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable, Protocol

from ..agents.execution_context import ExecutionContext
from ..core.extensions import db
from ..tools import calendar_tools
from .models import CalendarEvent


BLOCKING_TYPES = {"task_block", "meeting", "personal"}
SESSION_DONE = {"COMPLETED", "CANCELLED"}


@dataclass(frozen=True)
class TimeInterval:
    start: datetime
    end: datetime

    @property
    def minutes(self) -> int:
        return max(0, int((self.end - self.start).total_seconds() // 60))

    def to_dict(self) -> dict[str, str | int]:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "durationMinutes": self.minutes,
        }


class CalendarProvider(Protocol):
    def list_events(self, ctx: ExecutionContext, start: datetime, end: datetime) -> list[CalendarEvent]:
        ...

    def create_event(self, ctx: ExecutionContext, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def update_event(self, ctx: ExecutionContext, event_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def delete_event(self, ctx: ExecutionContext, event_id: str) -> dict[str, Any]:
        ...


class OraCalendarProvider:
    def list_events(self, ctx: ExecutionContext, start: datetime, end: datetime) -> list[CalendarEvent]:
        return CalendarEvent.query.filter(
            CalendarEvent.workspace_id == ctx.workspace_id,
            CalendarEvent.start_time < end,
            CalendarEvent.end_time > start,
        ).order_by(CalendarEvent.start_time.asc()).all()

    def create_event(self, ctx: ExecutionContext, payload: dict[str, Any]) -> dict[str, Any]:
        return calendar_tools.create_event(
            workspace_id=ctx.workspace_id,
            owner_id=ctx.user_id,
            title=payload["title"],
            start=payload["start"],
            end=payload["end"],
            event_type=payload.get("event_type", "personal"),
            scope=payload.get("scope", "personal"),
            task_id=payload.get("task_id"),
            color=payload.get("color", "blue"),
            timezone=payload.get("timezone", "UTC"),
            recurrence_rule=payload.get("recurrence_rule"),
            attendees=payload.get("attendees"),
            organization_id=payload.get("organization_id"),
        )

    def update_event(self, ctx: ExecutionContext, event_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return calendar_tools.update_event(
            event_id,
            title=payload.get("title"),
            start=payload.get("start"),
            end=payload.get("end"),
            color=payload.get("color"),
            scope=payload.get("scope"),
        )

    def delete_event(self, ctx: ExecutionContext, event_id: str) -> dict[str, Any]:
        return calendar_tools.delete_event(event_id, delete_series=False)


class CalendarService:
    def __init__(self, provider: CalendarProvider | None = None):
        self.provider = provider or OraCalendarProvider()

    def list_events(self, ctx: ExecutionContext, start: datetime, end: datetime) -> list[dict[str, Any]]:
        return [serialize_event(event) for event in self.provider.list_events(ctx, start, end)]

    def availability(
        self,
        ctx: ExecutionContext,
        start: datetime,
        end: datetime,
        *,
        day_start_hour: int = 9,
        day_end_hour: int = 18,
        weekdays_only: bool = False,
    ) -> list[dict[str, Any]]:
        events = self.provider.list_events(ctx, start, end)
        busy = [
            TimeInterval(event.start_time, event.end_time)
            for event in events
            if _is_blocking(event) and event.start_time and event.end_time
        ]
        free = compute_free_intervals(
            start, end, busy,
            day_start_hour=day_start_hour,
            day_end_hour=day_end_hour,
            weekdays_only=weekdays_only,
        )
        return [interval.to_dict() for interval in free]

    def create_event(
        self,
        ctx: ExecutionContext,
        payload: dict[str, Any],
        *,
        allow_overlap: bool = False,
    ) -> dict[str, Any]:
        conflict = self.conflict_for(ctx, payload["start"], payload["end"], event_type=payload.get("event_type"))
        if conflict and not allow_overlap:
            return {"success": False, "data": {"conflicts": conflict}, "error": "CONFLICT: calendar event overlaps existing blocking event"}
        result = self.provider.create_event(ctx, payload)
        if result.get("success"):
            event = db.session.get(CalendarEvent, result["data"]["id"])
            _apply_session_fields(event, payload)
            db.session.commit()
            result["data"] = serialize_event(event)
        return result

    def update_event(
        self,
        ctx: ExecutionContext,
        event_id: str,
        payload: dict[str, Any],
        *,
        allow_overlap: bool = False,
    ) -> dict[str, Any]:
        event = db.session.get(CalendarEvent, event_id)
        if not event:
            return {"success": False, "data": None, "error": f"Event {event_id} not found"}
        start = payload.get("start") or event.start_time
        end = payload.get("end") or event.end_time
        conflict = self.conflict_for(ctx, start, end, ignore_event_id=event_id, event_type=payload.get("event_type") or event.type)
        if conflict and not allow_overlap:
            return {"success": False, "data": {"conflicts": conflict}, "error": "CONFLICT: calendar event overlaps existing blocking event"}
        result = self.provider.update_event(ctx, event_id, payload)
        if result.get("success"):
            event = db.session.get(CalendarEvent, event_id)
            _apply_session_fields(event, payload)
            db.session.commit()
            result["data"] = serialize_event(event)
        return result

    def delete_event(self, ctx: ExecutionContext, event_id: str) -> dict[str, Any]:
        return self.provider.delete_event(ctx, event_id)

    def complete_session(self, ctx: ExecutionContext, event_id: str) -> dict[str, Any]:
        event = db.session.get(CalendarEvent, event_id)
        if not event or event.workspace_id != ctx.workspace_id:
            return {"success": False, "data": None, "error": f"Event {event_id} not found"}
        event.session_status = "COMPLETED"
        event.completed_at = datetime.utcnow()
        db.session.commit()
        return {"success": True, "data": serialize_event(event), "error": None}

    def mark_missed_sessions(self, ctx: ExecutionContext, now: datetime | None = None) -> list[dict[str, Any]]:
        now = now or datetime.utcnow()
        events = CalendarEvent.query.filter(
            CalendarEvent.workspace_id == ctx.workspace_id,
            CalendarEvent.task_id.isnot(None),
            CalendarEvent.end_time < now,
            CalendarEvent.session_status == "SCHEDULED",
        ).all()
        for event in events:
            event.session_status = "MISSED"
        if events:
            db.session.commit()
        return [serialize_event(event) for event in events]

    def conflict_for(
        self,
        ctx: ExecutionContext,
        start: datetime,
        end: datetime,
        *,
        ignore_event_id: str | None = None,
        event_type: str | None = None,
    ) -> list[dict[str, Any]]:
        if event_type and event_type not in BLOCKING_TYPES:
            return []
        events = CalendarEvent.query.filter(
            CalendarEvent.workspace_id == ctx.workspace_id,
            CalendarEvent.start_time < end,
            CalendarEvent.end_time > start,
        ).all()
        conflicts = [
            serialize_event(event)
            for event in events
            if event.id != ignore_event_id and _is_blocking(event)
        ]
        return conflicts


def compute_free_intervals(
    start: datetime,
    end: datetime,
    busy_intervals: Iterable[TimeInterval],
    *,
    day_start_hour: int = 9,
    day_end_hour: int = 18,
    weekdays_only: bool = False,
) -> list[TimeInterval]:
    busy = sorted((interval for interval in busy_intervals if interval.start < end and interval.end > start), key=lambda item: item.start)
    free: list[TimeInterval] = []
    day = start.replace(hour=0, minute=0, second=0, microsecond=0)
    while day < end:
        if weekdays_only and day.weekday() >= 5:
            day += timedelta(days=1)
            continue
        window_start = max(start, day.replace(hour=day_start_hour, minute=0, second=0, microsecond=0))
        window_end = min(end, day.replace(hour=day_end_hour, minute=0, second=0, microsecond=0))
        cursor = window_start
        for interval in busy:
            if interval.end <= cursor or interval.start >= window_end:
                continue
            if interval.start > cursor:
                free.append(TimeInterval(cursor, min(interval.start, window_end)))
            cursor = max(cursor, interval.end)
        if cursor < window_end:
            free.append(TimeInterval(cursor, window_end))
        day += timedelta(days=1)
    return [interval for interval in free if interval.minutes > 0]


def serialize_event(event: CalendarEvent | None) -> dict[str, Any]:
    if not event:
        return {}
    return {
        "id": event.id,
        "workspaceId": event.workspace_id,
        "ownerId": event.owner_id,
        "title": event.title,
        "start": event.start_time.isoformat() if event.start_time else None,
        "end": event.end_time.isoformat() if event.end_time else None,
        "type": event.type,
        "scope": event.scope,
        "taskId": event.task_id,
        "color": event.color,
        "timezone": event.timezone,
        "isFlexible": bool(getattr(event, "is_flexible", True)),
        "locked": bool(getattr(event, "locked", False)),
        "sessionStatus": getattr(event, "session_status", "SCHEDULED") or "SCHEDULED",
        "completedAt": event.completed_at.isoformat() if getattr(event, "completed_at", None) else None,
    }


def _is_blocking(event: CalendarEvent) -> bool:
    if getattr(event, "session_status", None) in SESSION_DONE:
        return False
    return event.type in BLOCKING_TYPES or bool(getattr(event, "locked", False))


def _apply_session_fields(event: CalendarEvent | None, payload: dict[str, Any]) -> None:
    if not event:
        return
    for attr, key in (
        ("is_flexible", "is_flexible"),
        ("locked", "locked"),
        ("session_status", "session_status"),
    ):
        if key in payload:
            setattr(event, attr, payload[key])
