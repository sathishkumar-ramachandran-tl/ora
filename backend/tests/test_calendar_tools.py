"""calendar_tools.py tests — recurrence expansion, availability-finding edge cases
(overlapping events, timezone boundaries), and scope enforcement (personal/workspace/company)."""
from datetime import datetime, timedelta

from app.core.extensions import db
from app.workspaces.models import Workspace, WorkspaceMember
from app.organizations.models import Organization, OrganizationMember
from app.auth.models import User
from app.core.security import hash_password
from app.tools import calendar_tools


def _make_user(id_, email):
    user = User(id=id_, email=email, name=email, password_hash=hash_password("pw"), email_verified=True)
    db.session.add(user)
    return user


def test_create_and_list_events_within_window(app, db):
    with app.app_context():
        owner = _make_user("cal-u1", "cal1@example.com")
        ws = Workspace(id="cal-ws1", name="WS1", context="personal", owner_id=owner.id)
        db.session.add(ws)
        db.session.commit()

        start = datetime(2026, 8, 10, 9, 0)
        end = datetime(2026, 8, 10, 10, 0)
        result = calendar_tools.create_event(ws.id, owner.id, "Standup", start, end)
        assert result["success"], result["error"]

        listed = calendar_tools.list_events(
            ws.id, owner.id, datetime(2026, 8, 10, 0, 0), datetime(2026, 8, 11, 0, 0),
        )
        assert listed["success"]
        assert len(listed["data"]) == 1
        assert listed["data"][0]["title"] == "Standup"
        assert listed["data"][0]["isRecurringOccurrence"] is False


def test_create_event_validates_required_domain_invariants(app, db):
    with app.app_context():
        owner = _make_user("cal-u-validation", "cal-validation@example.com")
        ws = Workspace(id="cal-ws-validation", name="WS validation", context="personal", owner_id=owner.id)
        db.session.add(ws)
        db.session.commit()

        result = calendar_tools.create_event(
            ws.id, owner.id, "Broken block",
            datetime(2026, 8, 10, 10, 0), datetime(2026, 8, 10, 9, 0),
        )
        assert not result["success"]
        assert "after start" in result["error"]

        result = calendar_tools.create_event(
            ws.id, owner.id, "Bad scope",
            datetime(2026, 8, 10, 9, 0), datetime(2026, 8, 10, 10, 0),
            scope="public",
        )
        assert not result["success"]
        assert "Invalid event scope" in result["error"]


def test_create_event_is_idempotent_for_identical_request(app, db):
    with app.app_context():
        owner = _make_user("cal-u-idempotent", "cal-idempotent@example.com")
        ws = Workspace(id="cal-ws-idempotent", name="WS idempotent", context="personal", owner_id=owner.id)
        db.session.add(ws)
        db.session.commit()

        start = datetime(2026, 8, 10, 9, 0)
        end = datetime(2026, 8, 10, 10, 0)
        first = calendar_tools.create_event(ws.id, owner.id, "Study block", start, end)
        second = calendar_tools.create_event(ws.id, owner.id, "Study block", start, end)

        assert first["success"], first["error"]
        assert second["success"], second["error"]
        assert second["data"]["status"] == "already_exists"
        assert second["data"]["id"] == first["data"]["id"]

        from app.calendar.models import CalendarEvent
        assert CalendarEvent.query.filter_by(workspace_id=ws.id, title="Study block").count() == 1


def test_update_event_rejects_invalid_window(app, db):
    with app.app_context():
        owner = _make_user("cal-u-update", "cal-update@example.com")
        ws = Workspace(id="cal-ws-update", name="WS update", context="personal", owner_id=owner.id)
        db.session.add(ws)
        db.session.commit()

        created = calendar_tools.create_event(
            ws.id, owner.id, "Update me",
            datetime(2026, 8, 10, 9, 0), datetime(2026, 8, 10, 10, 0),
        )
        result = calendar_tools.update_event(created["data"]["id"], end=datetime(2026, 8, 10, 8, 0))
        assert not result["success"]
        assert "after start" in result["error"]


def test_delete_event_returns_verified_operation_state(app, db):
    with app.app_context():
        owner = _make_user("cal-u-delete", "cal-delete@example.com")
        ws = Workspace(id="cal-ws-delete", name="WS delete", context="personal", owner_id=owner.id)
        db.session.add(ws)
        db.session.commit()

        created = calendar_tools.create_event(
            ws.id, owner.id, "Delete me",
            datetime(2026, 8, 10, 9, 0), datetime(2026, 8, 10, 10, 0),
        )
        result = calendar_tools.delete_event(created["data"]["id"])
        assert result["success"], result["error"]
        assert result["data"]["operationStatus"] == "succeeded"
        assert result["data"]["verified"] is True


def test_recurrence_expands_multiple_occurrences_in_window():
    """rrule expansion is pure-python (no DB), test the helper directly."""
    class FakeEvent:
        start_time = datetime(2026, 8, 3, 9, 0)  # a Monday
        end_time = datetime(2026, 8, 3, 10, 0)
        recurrence_rule = "FREQ=WEEKLY;BYDAY=MO,WE,FR;COUNT=6"

    window_start = datetime(2026, 8, 3, 0, 0)
    window_end = datetime(2026, 8, 14, 0, 0)  # two-week window
    occurrences = list(calendar_tools._expand_occurrences(FakeEvent(), window_start, window_end))
    # Mon 8/3, Wed 8/5, Fri 8/7, Mon 8/10, Wed 8/12 fall in-window (Fri 8/14 excluded by end-exclusive window)
    assert len(occurrences) == 5
    assert occurrences[0] == (datetime(2026, 8, 3, 9, 0), datetime(2026, 8, 3, 10, 0))
    assert occurrences[-1] == (datetime(2026, 8, 12, 9, 0), datetime(2026, 8, 12, 10, 0))


def test_recurrence_malformed_rule_degrades_to_single_occurrence():
    class FakeEvent:
        start_time = datetime(2026, 8, 3, 9, 0)
        end_time = datetime(2026, 8, 3, 10, 0)
        recurrence_rule = "NOT-A-VALID-RULE"

    occurrences = list(calendar_tools._expand_occurrences(
        FakeEvent(), datetime(2026, 8, 1), datetime(2026, 8, 5),
    ))
    assert occurrences == [(datetime(2026, 8, 3, 9, 0), datetime(2026, 8, 3, 10, 0))]


def test_delete_series_removes_all_recurrence_rows(app, db):
    with app.app_context():
        owner = _make_user("cal-u2", "cal2@example.com")
        ws = Workspace(id="cal-ws2", name="WS2", context="personal", owner_id=owner.id)
        db.session.add(ws)
        db.session.commit()

        master = calendar_tools.create_event(
            ws.id, owner.id, "Weekly sync",
            datetime(2026, 8, 3, 9, 0), datetime(2026, 8, 3, 10, 0),
            recurrence_rule="FREQ=WEEKLY;COUNT=4",
        )
        master_id = master["data"]["id"]

        from app.calendar.models import CalendarEvent
        occurrence = CalendarEvent(
            id="cal-occ-1", workspace_id=ws.id, owner_id=owner.id, title="Weekly sync",
            start_time=datetime(2026, 8, 10, 9, 0), end_time=datetime(2026, 8, 10, 10, 0),
            type="meeting", scope="personal", recurrence_parent_id=master_id,
        )
        db.session.add(occurrence)
        db.session.commit()

        result = calendar_tools.delete_event(master_id, delete_series=True)
        assert result["success"]
        assert set(result["data"]["deletedEventIds"]) == {master_id, "cal-occ-1"}
        assert db.session.get(CalendarEvent, master_id) is None
        assert db.session.get(CalendarEvent, "cal-occ-1") is None


def test_scope_personal_hidden_from_other_members(app, db):
    with app.app_context():
        owner = _make_user("cal-u3", "cal3@example.com")
        other = _make_user("cal-u4", "cal4@example.com")
        ws = Workspace(id="cal-ws3", name="WS3", context="personal", owner_id=owner.id)
        db.session.add(ws)
        db.session.add(WorkspaceMember(workspace_id=ws.id, user_id=other.id))
        db.session.commit()

        calendar_tools.create_event(
            ws.id, owner.id, "Private note",
            datetime(2026, 8, 10, 9, 0), datetime(2026, 8, 10, 10, 0), scope="personal",
        )

        owner_view = calendar_tools.list_events(ws.id, owner.id, datetime(2026, 8, 10), datetime(2026, 8, 11))
        other_view = calendar_tools.list_events(ws.id, other.id, datetime(2026, 8, 10), datetime(2026, 8, 11))
        assert len(owner_view["data"]) == 1
        assert len(other_view["data"]) == 0


def test_scope_workspace_visible_to_members(app, db):
    with app.app_context():
        owner = _make_user("cal-u5", "cal5@example.com")
        member = _make_user("cal-u6", "cal6@example.com")
        ws = Workspace(id="cal-ws4", name="WS4", context="personal", owner_id=owner.id)
        db.session.add(ws)
        db.session.add(WorkspaceMember(workspace_id=ws.id, user_id=member.id))
        db.session.commit()

        calendar_tools.create_event(
            ws.id, owner.id, "Team meeting",
            datetime(2026, 8, 10, 9, 0), datetime(2026, 8, 10, 10, 0), scope="workspace",
        )

        member_view = calendar_tools.list_events(ws.id, member.id, datetime(2026, 8, 10), datetime(2026, 8, 11))
        assert len(member_view["data"]) == 1


def test_scope_company_visible_to_org_members_across_workspaces(app, db):
    with app.app_context():
        owner = _make_user("cal-u7", "cal7@example.com")
        org_member = _make_user("cal-u8", "cal8@example.com")
        org = Organization(id="cal-org1", name="Org1", owner_id=owner.id)
        db.session.add(org)
        ws = Workspace(id="cal-ws5", name="WS5", context="company", owner_id=owner.id, organization_id=org.id)
        db.session.add(ws)
        db.session.add(OrganizationMember(organization_id=org.id, user_id=org_member.id, status="active"))
        db.session.commit()

        calendar_tools.create_event(
            ws.id, owner.id, "All-hands",
            datetime(2026, 8, 10, 9, 0), datetime(2026, 8, 10, 10, 0), scope="company",
            organization_id=org.id,
        )

        org_view = calendar_tools.list_events(ws.id, org_member.id, datetime(2026, 8, 10), datetime(2026, 8, 11))
        assert len(org_view["data"]) == 1

        # A non-member of the org should not see the company-scope event.
        outsider = _make_user("cal-u9", "cal9@example.com")
        db.session.commit()
        outsider_view = calendar_tools.list_events(ws.id, outsider.id, datetime(2026, 8, 10), datetime(2026, 8, 11))
        assert len(outsider_view["data"]) == 0


def test_find_availability_skips_busy_slots(app, db):
    with app.app_context():
        owner = _make_user("cal-u10", "cal10@example.com")
        ws = Workspace(id="cal-ws6", name="WS6", context="personal", owner_id=owner.id)
        db.session.add(ws)
        db.session.commit()

        # Busy 9:00-11:00 on 2026-08-10 (a Monday).
        calendar_tools.create_event(
            ws.id, owner.id, "Busy block",
            datetime(2026, 8, 10, 9, 0), datetime(2026, 8, 10, 11, 0),
        )

        result = calendar_tools.find_availability(
            ws.id, [owner.id], duration_minutes=60,
            window_start=datetime(2026, 8, 10, 9, 0), window_end=datetime(2026, 8, 10, 18, 0),
            day_start_hour=9, day_end_hour=18,
        )
        assert result["success"]
        slots = result["data"]["slots"]
        assert len(slots) > 0
        # No returned slot should overlap the 9-11 busy block.
        busy_start, busy_end = datetime(2026, 8, 10, 9, 0), datetime(2026, 8, 10, 11, 0)
        for slot in slots:
            s = datetime.fromisoformat(slot["start"])
            e = datetime.fromisoformat(slot["end"])
            assert not (s < busy_end and e > busy_start)
        assert slots[0]["start"] == "2026-08-10T11:00:00"


def test_find_availability_respects_working_hours_across_days(app, db):
    with app.app_context():
        owner = _make_user("cal-u11", "cal11@example.com")
        ws = Workspace(id="cal-ws7", name="WS7", context="personal", owner_id=owner.id)
        db.session.add(ws)
        db.session.commit()

        # Fill the entire working day so the next slot must land on day 2.
        calendar_tools.create_event(
            ws.id, owner.id, "All day busy",
            datetime(2026, 8, 10, 9, 0), datetime(2026, 8, 10, 18, 0),
        )

        result = calendar_tools.find_availability(
            ws.id, [owner.id], duration_minutes=60,
            window_start=datetime(2026, 8, 10, 9, 0), window_end=datetime(2026, 8, 11, 18, 0),
            day_start_hour=9, day_end_hour=18,
        )
        assert result["success"]
        slots = result["data"]["slots"]
        assert len(slots) > 0
        first_start = datetime.fromisoformat(slots[0]["start"])
        assert first_start.date() == datetime(2026, 8, 11).date()
        assert first_start.hour == 9


def test_schedule_module_milestones_creates_task_block_events(app, db):
    with app.app_context():
        owner = _make_user("cal-u12", "cal12@example.com")
        ws = Workspace(id="cal-ws8", name="WS8", context="personal", owner_id=owner.id)
        db.session.add(ws)
        db.session.commit()

        from app.modules.models import ModuleTemplate, ModuleTemplateVersion, ModuleInstance
        from app.projects.models import Company, Project, Milestone

        company = Company(id="cal-co1", name="Modules", workspace_id=ws.id)
        db.session.add(company)
        project = Project(id="cal-proj1", name="Test Module", company_id=company.id, workspace_id=ws.id)
        db.session.add(project)
        template = ModuleTemplate(
            id="cal-tmpl1", title="Test", slug="cal-test", description="", category="course",
            difficulty="beginner", is_published=False,
        )
        db.session.add(template)
        db.session.flush()
        version = ModuleTemplateVersion(
            id="cal-ver1", module_template_id=template.id, version=1,
            structure_json={}, generated_by="gemini", generation_status="ready",
        )
        db.session.add(version)
        instance = ModuleInstance(
            id="cal-inst1", module_template_id=template.id, module_template_version_id=version.id,
            workspace_id=ws.id, project_id=project.id, owner_id=owner.id, status="active",
        )
        db.session.add(instance)
        milestone = Milestone(
            id="cal-mile1", project_id=project.id, title="Week 1", description="",
            due_date=datetime.utcnow() + timedelta(days=3), status="pending", order=0,
        )
        db.session.add(milestone)
        db.session.commit()

        result = calendar_tools.schedule_module_milestones(instance.id, ws.id, owner.id, block_hours=2.0)
        assert result["success"], result["error"]
        assert result["data"]["scheduledCount"] == 1

        from app.calendar.models import CalendarEvent
        events = CalendarEvent.query.filter_by(workspace_id=ws.id, type="task_block").all()
        assert len(events) == 1
        assert "Week 1" in events[0].title


def test_schedule_module_milestones_fails_for_unknown_instance(app, db):
    with app.app_context():
        owner = _make_user("cal-u13", "cal13@example.com")
        ws = Workspace(id="cal-ws9", name="WS9", context="personal", owner_id=owner.id)
        db.session.add(ws)
        db.session.commit()

        result = calendar_tools.schedule_module_milestones("does-not-exist", ws.id, owner.id)
        assert not result["success"]


def test_find_availability_weekdays_only_skips_weekends(app, db):
    with app.app_context():
        owner = _make_user("cal-u14", "cal14@example.com")
        ws = Workspace(id="cal-ws10", name="WS10", context="personal", owner_id=owner.id)
        db.session.add(ws)
        db.session.commit()

        # 2026-08-14 is a Friday; the window runs through Sunday 8/16.
        result = calendar_tools.find_availability(
            ws.id, [owner.id], duration_minutes=60,
            window_start=datetime(2026, 8, 14, 17, 0), window_end=datetime(2026, 8, 16, 18, 0),
            day_start_hour=9, day_end_hour=18, weekdays_only=True,
        )
        assert result["success"]
        slots = result["data"]["slots"]
        assert len(slots) > 0
        assert all(datetime.fromisoformat(s["start"]).weekday() < 5 for s in slots)


def _seed_project(db, owner_id, ws_id="cal-ws-auto"):
    from app.projects.models import Company, Project
    company = Company(id=f"{ws_id}-co", name="Co", workspace_id=ws_id)
    db.session.add(company)
    project = Project(id=f"{ws_id}-proj", name="Proj", company_id=company.id, workspace_id=ws_id)
    db.session.add(project)
    db.session.commit()
    return project


def test_auto_schedule_tasks_places_open_tasks_into_free_slots(app, db):
    with app.app_context():
        owner = _make_user("cal-u15", "cal15@example.com")
        ws = Workspace(id="cal-ws-auto1", name="WS-Auto1", context="personal", owner_id=owner.id)
        db.session.add(ws)
        db.session.commit()
        project = _seed_project(db, owner.id, ws.id)

        from app.tools import task_tools
        t1 = task_tools.create_task(project.id, ws.id, "Task A", priority="high", estimated_hours=1.0)["data"]
        t2 = task_tools.create_task(project.id, ws.id, "Task B", priority="low", estimated_hours=1.0)["data"]

        result = calendar_tools.auto_schedule_tasks(ws.id, owner.id, day_start_hour=9, day_end_hour=18)
        assert result["success"], result["error"]
        assert result["data"]["scheduledCount"] == 2
        scheduled_ids = {s["taskId"] for s in result["data"]["scheduled"]}
        assert scheduled_ids == {t1["id"], t2["id"]}

        # Second scheduled task must not overlap the first (sequential placement).
        starts = sorted(datetime.fromisoformat(s["start"]) for s in result["data"]["scheduled"])
        assert starts[1] >= starts[0] + timedelta(hours=1)


def test_auto_schedule_tasks_skips_done_and_already_scheduled(app, db):
    with app.app_context():
        owner = _make_user("cal-u16", "cal16@example.com")
        ws = Workspace(id="cal-ws-auto2", name="WS-Auto2", context="personal", owner_id=owner.id)
        db.session.add(ws)
        db.session.commit()
        project = _seed_project(db, owner.id, ws.id)

        from app.tools import task_tools
        task_tools.create_task(project.id, ws.id, "Done task", status="done")
        open_task = task_tools.create_task(project.id, ws.id, "Open task", estimated_hours=1.0)["data"]

        already_scheduled = task_tools.create_task(project.id, ws.id, "Already scheduled", estimated_hours=1.0)["data"]
        calendar_tools.create_event(
            ws.id, owner.id, "Existing block",
            datetime(2026, 8, 10, 9, 0), datetime(2026, 8, 10, 10, 0), task_id=already_scheduled["id"],
        )

        result = calendar_tools.auto_schedule_tasks(ws.id, owner.id)
        assert result["success"]
        scheduled_ids = {s["taskId"] for s in result["data"]["scheduled"]}
        assert scheduled_ids == {open_task["id"]}


def test_auto_schedule_tasks_no_open_tasks_fails_cleanly(app, db):
    with app.app_context():
        owner = _make_user("cal-u17", "cal17@example.com")
        ws = Workspace(id="cal-ws-auto3", name="WS-Auto3", context="personal", owner_id=owner.id)
        db.session.add(ws)
        db.session.commit()

        result = calendar_tools.auto_schedule_tasks(ws.id, owner.id)
        assert not result["success"]
        assert "No tasks" in result["error"]


def test_auto_schedule_tasks_reports_unscheduled_when_no_slots_fit(app, db):
    with app.app_context():
        owner = _make_user("cal-u18", "cal18@example.com")
        ws = Workspace(id="cal-ws-auto4", name="WS-Auto4", context="personal", owner_id=owner.id)
        db.session.add(ws)
        db.session.commit()
        project = _seed_project(db, owner.id, ws.id)

        from app.tools import task_tools
        task = task_tools.create_task(project.id, ws.id, "Impossible task", estimated_hours=1.0)["data"]

        # A window that ends before "now" + working hours can start is infeasible
        # (targetEndDate strictly in the past relative to the actual schedule window).
        past_window = (datetime.utcnow() - timedelta(days=1)).isoformat()
        result = calendar_tools.auto_schedule_tasks(ws.id, owner.id, window_end=past_window)
        assert not result["success"]
        assert "future" in result["error"]


def test_auto_schedule_tasks_accepts_timezone_aware_target_end_date(app, db):
    """Regression test: the frontend sends targetEndDate via `new Date(...).toISOString()`,
    e.g. "2026-08-20T00:00:00.000Z" — timezone-aware and at midnight. This previously crashed
    with a naive/aware datetime comparison TypeError, and separately excluded the whole target
    day from the schedulable window because midnight was treated as day-start, not day-end."""
    with app.app_context():
        owner = _make_user("cal-u19", "cal19@example.com")
        ws = Workspace(id="cal-ws-auto5", name="WS-Auto5", context="personal", owner_id=owner.id)
        db.session.add(ws)
        db.session.commit()
        project = _seed_project(db, owner.id, ws.id)

        from app.tools import task_tools
        task = task_tools.create_task(project.id, ws.id, "Deadline task", estimated_hours=1.0)["data"]

        target = (datetime.utcnow() + timedelta(days=7)).date()
        aware_target_end_date = f"{target.isoformat()}T00:00:00.000Z"

        result = calendar_tools.auto_schedule_tasks(ws.id, owner.id, window_end=aware_target_end_date)
        assert result["success"], result.get("error")
        assert result["data"]["scheduledCount"] == 1
        assert result["data"]["scheduled"][0]["taskId"] == task["id"]


def test_parse_schedule_constraints_defaults_without_api_key(monkeypatch, app, db):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)
    result = calendar_tools.parse_schedule_constraints("weekdays 9 to 5, done by March 1")
    assert result == {"dayStartHour": 9, "dayEndHour": 18, "weekdaysOnly": True, "targetEndDate": None}


def test_parse_schedule_constraints_empty_instruction_returns_defaults():
    result = calendar_tools.parse_schedule_constraints("")
    assert result == {"dayStartHour": 9, "dayEndHour": 18, "weekdaysOnly": True, "targetEndDate": None}
