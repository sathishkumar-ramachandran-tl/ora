from datetime import datetime, timedelta

from app import models
from app.agents.execution_context import ExecutionContext, execution_context, get_execution_context
from app.agents.tools import create_calendar_event


def _seed_workspace(db, suffix="1", owner_id=None):
    user_id = owner_id or f"u{suffix}"
    user = models.User(id=user_id, email=f"{user_id}@example.com", name=f"User {suffix}")
    ws = models.Workspace(
        id=f"ws{suffix}",
        name=f"Workspace {suffix}",
        context="personal",
        type="project",
        owner_id=user_id,
    )
    company = models.Company(
        id=f"c{suffix}",
        workspace_id=ws.id,
        name=f"Initiative {suffix}",
        mission="m",
        color="indigo",
        whiteboard=[],
    )
    project = models.Project(
        id=f"p{suffix}",
        workspace_id=ws.id,
        company_id=company.id,
        name=f"Project {suffix}",
        type="build",
        progress=0,
        whiteboard=[],
    )
    db.session.add_all([user, ws])
    db.session.commit()
    db.session.add(company)
    db.session.commit()
    db.session.add(project)
    db.session.commit()
    return user, ws, project


def test_execution_context_is_context_local():
    ctx = ExecutionContext(request_id="r1", user_id="u1", workspace_id="ws1")
    assert get_execution_context(required=False) is None
    with execution_context(ctx):
        assert get_execution_context() == ctx
    assert get_execution_context(required=False) is None


def test_langchain_tool_ignores_llm_supplied_identity(db):
    _seed_workspace(db, "1", "u1")
    _seed_workspace(db, "2", "u2")
    ctx = ExecutionContext(
        request_id="r1",
        user_id="u1",
        workspace_id="ws1",
        session_id="s1",
        run_id="run1",
    )
    start = datetime.utcnow() + timedelta(hours=1)
    end = start + timedelta(hours=1)

    with execution_context(ctx):
        result = create_calendar_event.invoke({
            "workspace_id": "ws2",
            "owner_id": "u2",
            "title": "Trusted Identity Event",
            "start": start.isoformat(),
            "end": end.isoformat(),
        })

    assert "error" not in result
    event = db.session.get(models.CalendarEvent, result["id"])
    assert event.workspace_id == "ws1"
    assert event.owner_id == "u1"
