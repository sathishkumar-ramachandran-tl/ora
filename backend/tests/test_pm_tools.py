"""
Tests for the Phase 3 Agentic Project Management tools in app/tools/task_tools.py —
milestones, sprints, task dependencies (with cycle detection), blocked-task queries,
and AI replanning (which reuses the Core Intelligence Layer's compiled graph).
"""
from unittest.mock import patch

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


# --- Milestones ---

def test_milestone_crud_roundtrip(db):
    _seed(db)
    created = task_tools.create_milestone("p1", "Design Phase", description="d", order=1)
    assert created["success"] is True
    milestone_id = created["data"]["id"]
    assert created["data"]["projectId"] == "p1"

    listed = task_tools.list_milestones("p1")["data"]
    assert len(listed) == 1

    updated = task_tools.update_milestone(milestone_id, status="in_progress")
    assert updated["success"] is True
    assert updated["data"]["status"] == "in_progress"

    deleted = task_tools.delete_milestone(milestone_id)
    assert deleted["success"] is True
    assert task_tools.list_milestones("p1")["data"] == []


def test_delete_milestone_unlinks_tasks_without_deleting_them(db):
    _seed(db)
    milestone_id = task_tools.create_milestone("p1", "M1")["data"]["id"]
    task = task_tools.create_task("p1", "ws1", "Task 1")["data"]
    task_tools.update_task(task["id"], status="todo")
    m = models.Task.query.get(task["id"])
    m.milestone_id = milestone_id
    from app.core.extensions import db as _db
    _db.session.commit()

    task_tools.delete_milestone(milestone_id)

    refreshed = models.Task.query.get(task["id"])
    assert refreshed is not None
    assert refreshed.milestone_id is None


def test_create_milestone_missing_project_fails(db):
    result = task_tools.create_milestone("nonexistent", "M1")
    assert result["success"] is False
    assert "not found" in result["error"]


# --- Sprints ---

def test_sprint_crud_roundtrip(db):
    _seed(db)
    created = task_tools.create_sprint("p1", "Sprint 1", status="active")
    assert created["success"] is True
    sprint_id = created["data"]["id"]

    updated = task_tools.update_sprint(sprint_id, status="completed")
    assert updated["data"]["status"] == "completed"

    deleted = task_tools.delete_sprint(sprint_id)
    assert deleted["success"] is True
    assert task_tools.list_sprints("p1")["data"] == []


# --- Task dependencies / cycle detection ---

def test_add_task_dependency_roundtrip(db):
    _seed(db)
    t1 = task_tools.create_task("p1", "ws1", "Task A")["data"]["id"]
    t2 = task_tools.create_task("p1", "ws1", "Task B")["data"]["id"]

    dep = task_tools.add_task_dependency(t1, t2)
    assert dep["success"] is True
    assert dep["data"]["taskId"] == t1
    assert dep["data"]["dependsOnTaskId"] == t2

    deps = task_tools.get_task_dependencies(t1)["data"]
    assert len(deps["dependsOn"]) == 1
    assert deps["dependsOn"][0]["task"]["id"] == t2

    reverse_deps = task_tools.get_task_dependencies(t2)["data"]
    assert len(reverse_deps["blockedBy"]) == 1


def test_add_task_dependency_rejects_self_dependency(db):
    _seed(db)
    t1 = task_tools.create_task("p1", "ws1", "Task A")["data"]["id"]
    result = task_tools.add_task_dependency(t1, t1)
    assert result["success"] is False
    assert "itself" in result["error"]


def test_add_task_dependency_rejects_duplicate(db):
    _seed(db)
    t1 = task_tools.create_task("p1", "ws1", "Task A")["data"]["id"]
    t2 = task_tools.create_task("p1", "ws1", "Task B")["data"]["id"]
    task_tools.add_task_dependency(t1, t2)
    dup = task_tools.add_task_dependency(t1, t2)
    assert dup["success"] is False
    assert "already exists" in dup["error"]


def test_add_task_dependency_rejects_cycle(db):
    """A -> B -> C, then trying to add C -> A must be rejected (would close the cycle)."""
    _seed(db)
    a = task_tools.create_task("p1", "ws1", "A")["data"]["id"]
    b = task_tools.create_task("p1", "ws1", "B")["data"]["id"]
    c = task_tools.create_task("p1", "ws1", "C")["data"]["id"]

    assert task_tools.add_task_dependency(a, b)["success"] is True
    assert task_tools.add_task_dependency(b, c)["success"] is True

    cyclic = task_tools.add_task_dependency(c, a)
    assert cyclic["success"] is False
    assert "cycle" in cyclic["error"]


def test_remove_task_dependency(db):
    _seed(db)
    t1 = task_tools.create_task("p1", "ws1", "Task A")["data"]["id"]
    t2 = task_tools.create_task("p1", "ws1", "Task B")["data"]["id"]
    dep_id = task_tools.add_task_dependency(t1, t2)["data"]["id"]

    removed = task_tools.remove_task_dependency(dep_id)
    assert removed["success"] is True
    assert task_tools.get_task_dependencies(t1)["data"]["dependsOn"] == []


# --- Blocked tasks ---

def test_get_blocked_tasks_only_lists_incomplete_blockers(db):
    _seed(db)
    blocker_done = task_tools.create_task("p1", "ws1", "Done blocker", status="done")["data"]["id"]
    blocker_open = task_tools.create_task("p1", "ws1", "Open blocker")["data"]["id"]
    dependent = task_tools.create_task("p1", "ws1", "Dependent task")["data"]["id"]

    task_tools.add_task_dependency(dependent, blocker_done)
    task_tools.add_task_dependency(dependent, blocker_open)

    blocked = task_tools.get_blocked_tasks("p1")["data"]
    assert len(blocked) == 1
    assert blocked[0]["taskId"] == dependent
    blocker_ids = {b["id"] for b in blocked[0]["blockedByTasks"]}
    assert blocker_ids == {blocker_open}


def test_get_blocked_tasks_empty_when_no_open_blockers(db):
    _seed(db)
    t1 = task_tools.create_task("p1", "ws1", "Task A", status="done")["data"]["id"]
    t2 = task_tools.create_task("p1", "ws1", "Task B")["data"]["id"]
    task_tools.add_task_dependency(t2, t1)

    assert task_tools.get_blocked_tasks("p1")["data"] == []


# --- AI Replanning ---

def test_replan_project_missing_project_fails(db):
    result = task_tools.replan_project("nonexistent", "ws1", "u1", "add a testing milestone")
    assert result["success"] is False
    assert "not found" in result["error"]


def test_replan_project_invokes_orchestrator_and_summarizes_plan(db):
    _seed(db)

    class _FakeOrchestrator:
        def invoke(self, initial_state, config=None):
            return {
                "final_answer": "Added a Testing milestone with 2 tasks.",
                "plan": [
                    {"description": "Create Testing milestone", "status": "completed", "result": "ok"},
                ],
            }

    with patch("app.agents.graph_v2.create_orchestrator", return_value=_FakeOrchestrator()):
        result = task_tools.replan_project("p1", "ws1", "u1", "add a testing milestone")

    assert result["success"] is True
    assert result["data"]["summary"] == "Added a Testing milestone with 2 tasks."
    assert len(result["data"]["steps"]) == 1
    assert result["data"]["steps"][0]["status"] == "completed"


def test_replan_project_handles_orchestrator_exception(db):
    _seed(db)

    class _BrokenOrchestrator:
        def invoke(self, initial_state, config=None):
            raise RuntimeError("boom")

    with patch("app.agents.graph_v2.create_orchestrator", return_value=_BrokenOrchestrator()):
        result = task_tools.replan_project("p1", "ws1", "u1", "add a testing milestone")

    assert result["success"] is False
    assert "boom" in result["error"]
