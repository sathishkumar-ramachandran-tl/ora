from app import models
from app.agents.entity_resolution import ResolutionState, resolve_task
from app.agents.execution_context import ExecutionContext, execution_context
from app.tools import task_tools


def _seed_two_workspaces(db):
    u1 = models.User(id="u1", email="u1@example.com", name="User One")
    u2 = models.User(id="u2", email="u2@example.com", name="User Two")
    ws1 = models.Workspace(id="ws1", name="WS 1", context="personal", type="project", owner_id="u1")
    ws2 = models.Workspace(id="ws2", name="WS 2", context="personal", type="project", owner_id="u2")
    c1 = models.Company(id="c1", workspace_id="ws1", name="Initiative 1", mission="m", color="indigo", whiteboard=[])
    c2 = models.Company(id="c2", workspace_id="ws2", name="Initiative 2", mission="m", color="indigo", whiteboard=[])
    p1 = models.Project(id="p1", workspace_id="ws1", company_id="c1", name="Project 1", type="build", progress=0, whiteboard=[])
    p2 = models.Project(id="p2", workspace_id="ws2", company_id="c2", name="Project 2", type="build", progress=0, whiteboard=[])
    t2 = models.Task(
        id="t2",
        workspace_id="ws2",
        project_id="p2",
        title="Foreign task",
        description="",
        status="todo",
        priority="medium",
        estimated_hours=1,
        resources=[],
    )
    db.session.add_all([u1, u2, ws1, ws2])
    db.session.commit()
    db.session.add_all([c1, c2])
    db.session.commit()
    db.session.add_all([p1, p2])
    db.session.commit()
    db.session.add(t2)
    db.session.commit()
    return t2


def _ctx(scope_project_id=None, scope_task_id=None):
    return ExecutionContext(
        request_id="r1",
        user_id="u1",
        workspace_id="ws1",
        session_id="s1",
        run_id="run1",
        scope_level="task" if scope_task_id else "project" if scope_project_id else "workspace",
        scope_project_id=scope_project_id,
        scope_task_id=scope_task_id,
    )


def test_agent_context_blocks_cross_workspace_task_mutation(db):
    foreign_task = _seed_two_workspaces(db)
    with execution_context(_ctx()):
        result = task_tools.update_task(foreign_task.id, status="done")

    db.session.refresh(foreign_task)
    assert result["success"] is False
    assert "Unauthorized" in result["error"]
    assert foreign_task.status == "todo"


def test_ambiguous_task_resolution_refuses_unique_mutation_target(db):
    _seed_two_workspaces(db)
    t1 = models.Task(
        id="t1",
        workspace_id="ws1",
        project_id="p1",
        title="Networking Task",
        description="",
        status="todo",
        priority="medium",
        estimated_hours=1,
        resources=[],
    )
    t2 = models.Task(
        id="t1b",
        workspace_id="ws1",
        project_id="p1",
        title="Networking Task",
        description="",
        status="todo",
        priority="medium",
        estimated_hours=1,
        resources=[],
    )
    db.session.add_all([t1, t2])
    db.session.commit()

    result = resolve_task(_ctx(scope_project_id="p1"), reference="Networking Task")

    assert result.state == ResolutionState.AMBIGUOUS
    assert result.entity is None
    assert {item.id for item in result.matches} == {"t1", "t1b"}
