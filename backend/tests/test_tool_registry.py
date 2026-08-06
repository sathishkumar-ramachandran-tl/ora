"""
Tests for app/tools/task_tools.py — the shared registry both the LangChain
orchestrator (app/agents/tools.py) and the MCP server (app/mcp_server.py) call into.
One suite here covers both call paths, since they no longer have separate logic.
"""
from app.tools import task_tools
from app import models


def _seed(db):
    user = models.User(id="u1", email="t@example.com", name="Test")
    db.session.add(user)
    db.session.commit()
    ws = models.Workspace(id="ws1", name="Test WS", context="personal", type="project", owner_id="u1")
    db.session.add(ws)
    db.session.commit()
    company = models.Company(id="c1", workspace_id="ws1", name="Test Co", mission="m", color="indigo", whiteboard=[])
    db.session.add(company)
    db.session.commit()
    project = models.Project(id="p1", workspace_id="ws1", company_id="c1", name="Test Proj", type="build", progress=0, whiteboard=[])
    db.session.add(project)
    db.session.commit()


def test_create_task_returns_canonical_shape(db):
    _seed(db)
    result = task_tools.create_task("p1", "ws1", "My Task", priority="high")
    assert result["success"] is True
    assert result["error"] is None
    assert result["data"]["title"] == "My Task"
    assert result["data"]["status"] == "created"


def test_update_and_delete_task_roundtrip(db):
    _seed(db)
    created = task_tools.create_task("p1", "ws1", "Roundtrip Task")
    task_id = created["data"]["id"]

    updated = task_tools.update_task(task_id, status="in-progress")
    assert updated["success"] is True
    assert updated["data"]["status"] == "updated"

    tasks = task_tools.get_tasks("ws1")["data"]
    assert len(tasks) == 1
    assert tasks[0]["status"] == "in-progress"

    deleted = task_tools.delete_task(task_id)
    assert deleted["success"] is True
    assert deleted["data"]["deleted_task_id"] == task_id

    tasks_after = task_tools.get_tasks("ws1")["data"]
    assert tasks_after == []


def test_update_task_not_found_returns_failure_shape(db):
    result = task_tools.update_task("nonexistent-id", status="done")
    assert result["success"] is False
    assert result["data"] is None
    assert "not found" in result["error"]


def test_update_task_assignee_id_persists(db):
    _seed(db)
    assignee = models.User(id="u2", email="assignee@example.com", name="Assignee")
    db.session.add(assignee)
    db.session.commit()

    created = task_tools.create_task("p1", "ws1", "Assign me")
    task_id = created["data"]["id"]

    updated = task_tools.update_task(task_id, assignee_id="u2")
    assert updated["success"] is True

    task = db.session.get(models.Task, task_id)
    assert task.assignee_id == "u2"


def test_list_workspace_members_returns_id_name_email(db):
    _seed(db)
    member = models.User(id="u2", email="member@example.com", name="Member Two")
    db.session.add(member)
    db.session.add(models.WorkspaceMember(workspace_id="ws1", user_id="u2", role_id="member"))
    db.session.commit()

    result = task_tools.list_workspace_members("ws1")
    assert result["success"] is True
    assert result["data"] == [{"id": "u2", "name": "Member Two", "email": "member@example.com"}]


def test_list_workspace_members_unknown_workspace_fails(db):
    result = task_tools.list_workspace_members("no-such-ws")
    assert result["success"] is False


def test_create_multiple_tasks_invalid_json_fails_cleanly(db):
    _seed(db)
    result = task_tools.create_multiple_tasks("p1", "ws1", "not valid json")
    assert result["success"] is False
    assert "Invalid JSON" in result["error"]


def test_analyze_workspace_progress_computes_completion_rate(db):
    _seed(db)
    t1 = task_tools.create_task("p1", "ws1", "Task 1", status="done")["data"]["id"]
    task_tools.create_task("p1", "ws1", "Task 2", status="todo", priority="critical")

    analysis = task_tools.analyze_workspace_progress("ws1")["data"]
    assert analysis["total_tasks"] == 2
    assert analysis["completed"] == 1
    assert analysis["completion_rate"] == 50.0
    assert len(analysis["overdue_high_priority"]) == 1
