from datetime import datetime, timedelta

from app import models
from app.agents.action_executor import execute_action
from app.agents.adaptation import (
    ImpactDecision,
    adapt_from_signal,
    plan_health,
    retrieval_benchmark,
    signal_from_mastery,
)
from app.agents.execution_context import ExecutionContext, execution_context
from app.agents.mastery import record_competency_evidence
from app.agents.scheduling import apply_schedule_proposal, create_schedule_proposal
from app.agents.undo import undo_action
from app.tools import task_tools


def _seed(db):
    user = models.User(id="u1", email="u1@example.com", name="User One")
    ws = models.Workspace(id="ws1", name="WS 1", context="personal", type="study", owner_id="u1", settings={})
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


def _task(db, task_id, title, hours=1.0, priority="medium", status="todo", due=None):
    task = models.Task(
        id=task_id,
        workspace_id="ws1",
        project_id="p1",
        title=title,
        status=status,
        priority=priority,
        estimated_hours=hours,
        due_date=due,
        resources=[],
        labels=[],
    )
    db.session.add(task)
    db.session.commit()
    return task


def _ctx(run_id="run-adapt"):
    return ExecutionContext(
        request_id=f"req-{run_id}",
        user_id="u1",
        workspace_id="ws1",
        session_id="s1",
        run_id=run_id,
        scope_project_id="p1",
    )


def test_failed_prerequisite_creates_local_adaptive_schedule_revision(db):
    _seed(db)
    _task(db, "cidr", "CIDR Aggregation", hours=1)
    _task(db, "bgp", "BGP Lab", hours=1, priority="critical")
    db.session.add(models.TaskDependency(task_id="bgp", depends_on_task_id="cidr", type="blocks"))
    db.session.commit()
    ctx = _ctx("run-failed-prereq")
    with execution_context(ctx):
        base = create_schedule_proposal(
            ctx,
            task_ids=["cidr", "bgp"],
            window_start=datetime(2026, 8, 17, 9),
            window_end=datetime(2026, 8, 22, 12),
            day_start_hour=9,
            day_end_hour=12,
        )
        apply_schedule_proposal(base.id)
        _, mastery = record_competency_evidence(
            ctx,
            concept_name="CIDR Aggregation",
            domain="computer_networks",
            evidence_type="assessment",
            result={"passed": False, "score": 0.4},
            strength="MODERATE",
        )
        decision = adapt_from_signal(ctx, signal_from_mastery(mastery))

    assert decision["impact"] == ImpactDecision.SCHEDULE_REVISION.value
    revision = decision["schedule_revision"]
    assert revision["supersedesId"] == base.id
    assert any("cidr aggregation review" == s["title"].lower() for s in revision["sessions"])
    assert revision["summary"]["adaptation"]["operations"][0]["op"] == "ADD"


def test_mastery_aware_scheduler_prioritizes_existing_review_task(db):
    _seed(db)
    _task(db, "cidr", "CIDR Aggregation practice", hours=1, priority="low")
    _task(db, "bgp", "BGP Lab", hours=1, priority="critical")
    ctx = _ctx("run-mastery-order")
    with execution_context(ctx):
        record_competency_evidence(
            ctx,
            concept_name="CIDR Aggregation",
            domain="computer_networks",
            evidence_type="assessment",
            result={"passed": False},
        )
        proposal = create_schedule_proposal(
            ctx,
            task_ids=["bgp", "cidr"],
            window_start=datetime(2026, 8, 17, 9),
            window_end=datetime(2026, 8, 18, 12),
            day_start_hour=9,
            day_end_hour=12,
        )
    assert proposal.sessions[0]["task_id"] == "cidr"


def test_plan_health_detects_capacity_risk(db):
    _seed(db)
    deadline = datetime.utcnow() + timedelta(days=1)
    _task(db, "large", "Overloaded work", hours=20, due=deadline)
    ctx = _ctx("run-capacity")
    with execution_context(ctx):
        health = plan_health(ctx)
    assert health["status"] == "REVISION_RECOMMENDED"
    assert health["capacity"]["at_risk"] is True


def test_retrieval_benchmark_uses_structured_resources_without_vector_requirement(db):
    _seed(db)
    _task(db, "cidr", "CIDR Review", hours=0.5)
    db.session.add(models.CalendarEvent(
        id="exam",
        workspace_id="ws1",
        owner_id="u1",
        title="Friday exam",
        start_time=datetime(2026, 8, 21, 10),
        end_time=datetime(2026, 8, 21, 11),
        type="meeting",
        scope="personal",
    ))
    db.session.commit()
    ctx = _ctx("run-retrieval")
    result = retrieval_benchmark(ctx)
    cidr = next(item for item in result["results"] if item["query"] == "CIDR")
    exam = next(item for item in result["results"] if item["query"] == "Friday exam")
    assert cidr["hit_count"] >= 1
    assert exam["hit_count"] >= 1
    assert "Do not add vector retrieval yet" in result["decision"]


def test_task_update_undo_and_repeated_undo_are_bounded(db):
    _seed(db)
    _task(db, "t1", "Routing Lab", hours=1, status="todo")
    ctx = _ctx("run-task-undo")
    with execution_context(ctx):
        execute_action(
            "task.update",
            "update_task_status",
            {"task_id": "t1", "new_status": "done"},
            lambda: task_tools.update_task_status("t1", "done"),
            action_id="task-update-action",
            before=lambda: {
                "id": "t1",
                "title": "Routing Lab",
                "description": None,
                "status": "todo",
                "priority": "medium",
                "estimated_hours": 1.0,
                "is_daily_focus": False,
                "assignee_id": None,
            },
        )
        first = undo_action("task-update-action")
        second = undo_action("task-update-action")
    assert first["success"] is True
    assert second["success"] is True
    assert db.session.get(models.Task, "t1").status == "todo"
    assert models.AgentAction.query.filter(models.AgentAction.id.like("undo_task-update-action%")).count() == 1
