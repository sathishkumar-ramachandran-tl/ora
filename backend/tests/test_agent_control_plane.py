from app import models
from app.agents.action_executor import create_agent_run, execute_action
from app.agents.control_plane import (
    ActionStatus,
    AgentRunStatus,
    ErrorClass,
    VerificationStatus,
)
from app.agents.execution_context import ExecutionContext, execution_context
from app.tools import task_tools


def _seed(db):
    user = models.User(id="u1", email="u1@example.com", name="User One")
    ws = models.Workspace(id="ws1", name="WS 1", context="personal", type="project", owner_id="u1")
    company = models.Company(id="c1", workspace_id="ws1", name="Initiative", mission="m", color="indigo", whiteboard=[])
    project = models.Project(id="p1", workspace_id="ws1", company_id="c1", name="Project", type="build", progress=0, whiteboard=[])
    db.session.add_all([user, ws])
    db.session.commit()
    db.session.add(company)
    db.session.commit()
    db.session.add(project)
    db.session.commit()
    return project


def _ctx(run_id="run1"):
    return ExecutionContext(
        request_id=f"req-{run_id}",
        user_id="u1",
        workspace_id="ws1",
        session_id="s1",
        run_id=run_id,
    )


def test_same_action_retry_creates_one_task(db):
    _seed(db)
    ctx = _ctx("run-retry")
    args = {"project_id": "p1", "workspace_id": "ws1", "title": "Read Chapter 4"}

    with execution_context(ctx):
        first = execute_action(
            "task.create",
            "create_task",
            args,
            lambda: task_tools.create_task("p1", "ws1", "Read Chapter 4"),
            action_id="act-retry",
        )
        second = execute_action(
            "task.create",
            "create_task",
            args,
            lambda: task_tools.create_task("p1", "ws1", "Read Chapter 4"),
            action_id="act-retry",
        )

    assert first["success"] is True
    assert second["success"] is True
    assert models.Task.query.filter_by(title="Read Chapter 4").count() == 1
    assert models.AgentToolCall.query.filter_by(action_id="act-retry").count() == 1


def test_distinct_actions_with_identical_args_create_legitimate_duplicates(db):
    _seed(db)
    ctx = _ctx("run-dupes")
    args = {"project_id": "p1", "workspace_id": "ws1", "title": "Read Chapter 4"}

    with execution_context(ctx):
        execute_action(
            "task.create",
            "create_task",
            args,
            lambda: task_tools.create_task("p1", "ws1", "Read Chapter 4"),
            action_id="act-one",
        )
        execute_action(
            "task.create",
            "create_task",
            args,
            lambda: task_tools.create_task("p1", "ws1", "Read Chapter 4"),
            action_id="act-two",
        )

    assert models.Task.query.filter_by(title="Read Chapter 4").count() == 2


def test_false_success_is_not_marked_verified(db):
    _seed(db)
    ctx = _ctx("run-false-success")
    with execution_context(ctx):
        result = execute_action(
            "task.create",
            "create_task",
            {"title": "Ghost task"},
            lambda: {"success": True, "data": {"id": "missing", "title": "Ghost task"}, "error": None},
            action_id="act-false-success",
            verify=lambda data: False,
        )

    assert result["success"] is True
    action = db.session.get(models.AgentAction, "act-false-success")
    tool_call = models.AgentToolCall.query.filter_by(action_id="act-false-success").one()
    assert action.status == ActionStatus.UNKNOWN.value
    assert tool_call.verification_status == VerificationStatus.FAILED.value
    assert action.after_state["error"] == "Verification failed"


def test_partial_completion_preserves_child_action_states(db):
    _seed(db)
    ctx = _ctx("run-partial")
    with execution_context(ctx):
        create_agent_run(ctx)
        execute_action(
            "task.create",
            "create_task",
            {"title": "One"},
            lambda: task_tools.create_task("p1", "ws1", "One"),
            action_id="partial-one",
        )
        execute_action(
            "task.create",
            "create_task",
            {"title": ""},
            lambda: {"success": False, "data": None, "error": "Validation error: title required"},
            action_id="partial-two",
        )
        execute_action(
            "task.create",
            "create_task",
            {"title": "Three"},
            lambda: task_tools.create_task("p1", "ws1", "Three"),
            action_id="partial-three",
        )

    run = db.session.get(models.AgentRun, "run-partial")
    assert run.status == AgentRunStatus.PARTIALLY_COMPLETED.value
    assert db.session.get(models.AgentAction, "partial-one").status == ActionStatus.SUCCEEDED.value
    assert db.session.get(models.AgentAction, "partial-two").after_state["error_class"] == ErrorClass.VALIDATION.value
    assert db.session.get(models.AgentAction, "partial-three").status == ActionStatus.SUCCEEDED.value


def test_non_retryable_failure_is_not_reexecuted(db):
    _seed(db)
    ctx = _ctx("run-loop")
    calls = {"count": 0}

    def fail_validation():
        calls["count"] += 1
        return {"success": False, "data": None, "error": "Validation error: bad input"}

    with execution_context(ctx):
        first = execute_action("task.create", "create_task", {"title": ""}, fail_validation, action_id="act-loop")
        second = execute_action("task.create", "create_task", {"title": ""}, fail_validation, action_id="act-loop")

    assert first["success"] is False
    assert second["success"] is False
    assert calls["count"] == 1
    assert models.AgentToolCall.query.filter_by(action_id="act-loop").count() == 1
