from datetime import datetime, timedelta

from app import models
from app.agents.action_executor import execute_action
from app.agents.execution_context import ExecutionContext, execution_context
from app.agents.scheduling import (
    apply_schedule_proposal,
    complete_calendar_session,
    create_schedule_proposal,
    create_schedule_revision,
    detect_missed_sessions,
)
from app.agents.undo import undo_action
from app.calendar.service import CalendarService, TimeInterval, compute_free_intervals, serialize_event


def _seed(db):
    user = models.User(id="u1", email="u1@example.com", name="User One")
    ws = models.Workspace(id="ws1", name="WS 1", context="personal", type="study", owner_id="u1")
    company = models.Company(id="c1", workspace_id="ws1", name="Learning", mission="m", color="indigo", whiteboard=[])
    project = models.Project(id="p1", workspace_id="ws1", company_id="c1", name="Computer Networks", type="learning", progress=0, whiteboard=[])
    db.session.add_all([user, ws])
    db.session.commit()
    db.session.add(models.WorkspaceMember(workspace_id="ws1", user_id="u1", role_id="owner"))
    db.session.add(company)
    db.session.commit()
    db.session.add(project)
    db.session.commit()
    return project


def _task(db, task_id, title, hours=1.0, priority="medium", status="todo"):
    task = models.Task(
        id=task_id,
        workspace_id="ws1",
        project_id="p1",
        title=title,
        status=status,
        priority=priority,
        estimated_hours=hours,
        resources=[],
    )
    db.session.add(task)
    db.session.commit()
    return task


def _ctx(run_id="run-schedule"):
    return ExecutionContext(
        request_id=f"req-{run_id}",
        user_id="u1",
        workspace_id="ws1",
        session_id="s1",
        run_id=run_id,
    )


def test_availability_computes_free_intervals():
    start = datetime(2026, 8, 17, 8)
    end = datetime(2026, 8, 17, 13)
    free = compute_free_intervals(
        start,
        end,
        [
            TimeInterval(datetime(2026, 8, 17, 9), datetime(2026, 8, 17, 10)),
            TimeInterval(datetime(2026, 8, 17, 11), datetime(2026, 8, 17, 12)),
        ],
        day_start_hour=8,
        day_end_hour=13,
    )
    assert [(i.start.hour, i.end.hour) for i in free] == [(8, 9), (10, 11), (12, 13)]


def test_overlap_returns_conflict(db):
    _seed(db)
    ctx = _ctx("run-conflict")
    with execution_context(ctx):
        first = CalendarService().create_event(ctx, {
            "title": "Fixed meeting",
            "start": datetime(2026, 8, 17, 10),
            "end": datetime(2026, 8, 17, 11),
            "event_type": "meeting",
            "locked": True,
            "is_flexible": False,
        })
        second = CalendarService().create_event(ctx, {
            "title": "Study block",
            "start": datetime(2026, 8, 17, 10, 30),
            "end": datetime(2026, 8, 17, 11, 30),
            "event_type": "task_block",
        })
    assert first["success"] is True
    assert second["success"] is False
    assert "CONFLICT" in second["error"]


def test_multi_session_task_splits_without_exceeding_effort(db):
    _seed(db)
    _task(db, "t1", "TCP Congestion Control", hours=3)
    ctx = _ctx("run-multi")
    with execution_context(ctx):
        proposal = create_schedule_proposal(
            ctx,
            task_ids=["t1"],
            window_start=datetime(2026, 8, 17, 9),
            window_end=datetime(2026, 8, 21, 18),
            constraints=[
                {"type": "unavailable_weekday", "weekday": 2},
                {"type": "unavailable_weekday", "weekday": 4},
            ],
            day_start_hour=9,
            day_end_hour=10,
            weekdays_only=True,
        )
    assert proposal.status == "READY"
    assert len(proposal.sessions) == 3
    assert sum(s["duration_minutes"] for s in proposal.sessions) == 180
    assert [datetime.fromisoformat(s["start_at"]).weekday() for s in proposal.sessions] == [0, 1, 3]


def test_dependency_order_schedules_prerequisite_first(db):
    _seed(db)
    _task(db, "a", "Routing Fundamentals", hours=1, priority="low")
    _task(db, "b", "BGP Policy", hours=1, priority="critical")
    db.session.add(models.TaskDependency(task_id="b", depends_on_task_id="a", type="blocks"))
    db.session.commit()
    ctx = _ctx("run-deps")
    with execution_context(ctx):
        proposal = create_schedule_proposal(
            ctx,
            task_ids=["b", "a"],
            window_start=datetime(2026, 8, 17, 9),
            window_end=datetime(2026, 8, 18, 12),
            day_start_hour=9,
            day_end_hour=12,
        )
    first = proposal.sessions[0]
    second = proposal.sessions[1]
    assert first["task_id"] == "a"
    assert second["task_id"] == "b"
    assert datetime.fromisoformat(first["end_at"]) <= datetime.fromisoformat(second["start_at"])


def test_infeasible_schedule_does_not_overbook(db):
    _seed(db)
    _task(db, "t1", "Large workload", hours=10)
    ctx = _ctx("run-infeasible")
    with execution_context(ctx):
        proposal = create_schedule_proposal(
            ctx,
            task_ids=["t1"],
            window_start=datetime(2026, 8, 17, 9),
            window_end=datetime(2026, 8, 17, 14),
            day_start_hour=9,
            day_end_hour=14,
            weekdays_only=False,
        )
    assert proposal.status == "INFEASIBLE"
    assert proposal.summary["requiredMinutes"] == 600
    assert proposal.summary["availableMinutes"] == 300
    assert sum(s["duration_minutes"] for s in proposal.sessions) <= 300


def test_schedule_apply_is_idempotent(db):
    _seed(db)
    _task(db, "t1", "CIDR Review", hours=1)
    ctx = _ctx("run-apply")
    with execution_context(ctx):
        proposal = create_schedule_proposal(
            ctx,
            task_ids=["t1"],
            window_start=datetime(2026, 8, 17, 9),
            window_end=datetime(2026, 8, 18, 12),
            day_start_hour=9,
            day_end_hour=12,
        )
        first = apply_schedule_proposal(proposal.id)
        second = apply_schedule_proposal(proposal.id)
    assert first["data"]["status"] == "APPLIED"
    assert second["data"]["status"] == "APPLIED"
    assert models.CalendarEvent.query.filter_by(task_id="t1").count() == 1


def test_hard_constraint_fixed_exam_unchanged_on_revision(db):
    _seed(db)
    _task(db, "t1", "TCP Review", hours=1)
    exam_start = datetime(2026, 8, 21, 10)
    exam_end = datetime(2026, 8, 21, 11)
    exam = models.CalendarEvent(
        id="exam",
        workspace_id="ws1",
        owner_id="u1",
        title="Final Exam",
        start_time=exam_start,
        end_time=exam_end,
        type="meeting",
        scope="personal",
        locked=True,
        is_flexible=False,
        session_status="SCHEDULED",
    )
    db.session.add(exam)
    db.session.commit()
    ctx = _ctx("run-hard")
    with execution_context(ctx):
        base = create_schedule_proposal(
            ctx,
            task_ids=["t1"],
            window_start=datetime(2026, 8, 17, 9),
            window_end=datetime(2026, 8, 22, 18),
            day_start_hour=9,
            day_end_hour=12,
        )
        revision = create_schedule_revision(ctx, base.id, unavailable_weekdays=["Wednesday"], fixed_event_ids=["exam"])
    refreshed = db.session.get(models.CalendarEvent, "exam")
    assert refreshed.start_time == exam_start
    assert refreshed.end_time == exam_end
    assert any(c.get("event_id") == "exam" for c in revision.constraints)


def test_partial_apply_preserves_successes_and_failures(db):
    _seed(db)
    _task(db, "t1", "TCP", hours=2)
    ctx = _ctx("run-partial")
    with execution_context(ctx):
        proposal = create_schedule_proposal(
            ctx,
            task_ids=["t1"],
            window_start=datetime(2026, 8, 17, 9),
            window_end=datetime(2026, 8, 18, 12),
            day_start_hour=9,
            day_end_hour=12,
        )
        failed_ref = proposal.sessions[0]["session_ref"]
        result = apply_schedule_proposal(proposal.id, fail_refs={failed_ref})
    assert result["data"]["status"] == "PARTIALLY_APPLIED"
    assert result["data"]["applicationResult"]["failures"] == 1
    assert models.AgentAction.query.filter(models.AgentAction.id.like(f"schedule_{proposal.id}_v1_%")).count() == len(proposal.sessions)


def test_today_prefers_task_that_fits_current_free_period(db):
    from app.agents.today import recommend_today

    _seed(db)
    _task(db, "short", "CIDR Review", hours=0.5, priority="medium")
    _task(db, "long", "BGP Lab", hours=1.5, priority="medium")
    ctx = _ctx("run-today")
    result = recommend_today(ctx, {"available_minutes": 45})
    assert result["now"]["task_id"] == "short"


def test_session_completion_does_not_complete_parent_task(db):
    _seed(db)
    task = _task(db, "t1", "Multi-session task", hours=3)
    event = models.CalendarEvent(
        id="e1",
        workspace_id="ws1",
        owner_id="u1",
        title="Session one",
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow() + timedelta(minutes=45),
        type="task_block",
        scope="personal",
        task_id="t1",
        session_status="SCHEDULED",
    )
    db.session.add(event)
    db.session.commit()
    ctx = _ctx("run-complete-session")
    with execution_context(ctx):
        complete_calendar_session(ctx, "e1")
    assert db.session.get(models.CalendarEvent, "e1").session_status == "COMPLETED"
    assert db.session.get(models.Task, task.id).status == "todo"


def test_missed_session_is_seen_without_completing_task(db):
    _seed(db)
    task = _task(db, "t1", "Past session task", hours=1)
    event = models.CalendarEvent(
        id="past",
        workspace_id="ws1",
        owner_id="u1",
        title="Missed session",
        start_time=datetime.utcnow() - timedelta(hours=2),
        end_time=datetime.utcnow() - timedelta(hours=1),
        type="task_block",
        scope="personal",
        task_id="t1",
        session_status="SCHEDULED",
    )
    db.session.add(event)
    db.session.commit()
    ctx = _ctx("run-missed")
    missed = detect_missed_sessions(ctx, now=datetime.utcnow())
    assert missed[0]["id"] == "past"
    assert db.session.get(models.CalendarEvent, "past").session_status == "MISSED"
    assert db.session.get(models.Task, task.id).status == "todo"


def test_undo_create_event_removes_event(db):
    _seed(db)
    ctx = _ctx("run-undo-create")
    with execution_context(ctx):
        result = execute_action(
            "calendar.event.create",
            "calendar.event.create",
            {"title": "Undo me"},
            lambda: CalendarService().create_event(ctx, {
                "title": "Undo me",
                "start": datetime(2026, 8, 17, 9),
                "end": datetime(2026, 8, 17, 10),
                "event_type": "task_block",
            }),
            action_id="create-event-action",
        )
        event_id = result["data"]["id"]
        undo = undo_action("create-event-action")
    assert undo["success"] is True
    assert db.session.get(models.CalendarEvent, event_id) is None


def test_undo_update_event_restores_prior_state(db):
    _seed(db)
    ctx = _ctx("run-undo-update")
    event = models.CalendarEvent(
        id="e1",
        workspace_id="ws1",
        owner_id="u1",
        title="TCP Review",
        start_time=datetime(2026, 8, 17, 18),
        end_time=datetime(2026, 8, 17, 19),
        type="task_block",
        scope="personal",
        session_status="SCHEDULED",
    )
    db.session.add(event)
    db.session.commit()
    with execution_context(ctx):
        execute_action(
            "calendar.event.update",
            "calendar.event.update",
            {"event_id": "e1"},
            lambda: CalendarService().update_event(ctx, "e1", {
                "start": datetime(2026, 8, 17, 20),
                "end": datetime(2026, 8, 17, 21),
            }),
            action_id="update-event-action",
            before=lambda: serialize_event(db.session.get(models.CalendarEvent, "e1")),
        )
        undo = undo_action("update-event-action")
    assert undo["success"] is True
    restored = db.session.get(models.CalendarEvent, "e1")
    assert restored.start_time == datetime(2026, 8, 17, 18)
    assert restored.end_time == datetime(2026, 8, 17, 19)


def test_undo_update_conflict_refuses_blind_restore(db):
    _seed(db)
    ctx = _ctx("run-undo-conflict")
    event = models.CalendarEvent(
        id="e1",
        workspace_id="ws1",
        owner_id="u1",
        title="TCP Review",
        start_time=datetime(2026, 8, 17, 18),
        end_time=datetime(2026, 8, 17, 19),
        type="task_block",
        scope="personal",
        session_status="SCHEDULED",
    )
    db.session.add(event)
    db.session.commit()
    with execution_context(ctx):
        execute_action(
            "calendar.event.update",
            "calendar.event.update",
            {"event_id": "e1"},
            lambda: CalendarService().update_event(ctx, "e1", {
                "start": datetime(2026, 8, 17, 20),
                "end": datetime(2026, 8, 17, 21),
            }),
            action_id="update-conflict-action",
            before=lambda: serialize_event(db.session.get(models.CalendarEvent, "e1")),
        )
        event = db.session.get(models.CalendarEvent, "e1")
        event.start_time = datetime(2026, 8, 17, 21)
        event.end_time = datetime(2026, 8, 17, 22)
        db.session.commit()
        undo = undo_action("update-conflict-action")
    assert undo["success"] is False
    assert "CONFLICT" in undo["error"]
    assert db.session.get(models.CalendarEvent, "e1").start_time == datetime(2026, 8, 17, 21)
