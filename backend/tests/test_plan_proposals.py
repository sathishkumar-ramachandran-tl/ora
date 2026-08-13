import json

from flask_jwt_extended import create_access_token

from app import models
from app.agents.action_executor import create_agent_run
from app.agents.context import build_context_envelope
from app.agents.control_plane import ActionStatus
from app.agents.execution_context import ExecutionContext, execution_context
from app.agents.planning import (
    PlanStatus,
    QualityStatus,
    apply_plan_proposal,
    create_plan_proposal,
    request_plan_confirmation,
)


def _seed(db, *, second_workspace=False):
    u1 = models.User(id="u1", email="u1@example.com", name="User One")
    ws1 = models.Workspace(id="ws1", name="WS 1", context="personal", type="project", owner_id="u1")
    c1 = models.Company(id="c1", workspace_id="ws1", name="Initiative", mission="m", color="indigo", whiteboard=[])
    p1 = models.Project(id="p1", workspace_id="ws1", company_id="c1", name="Computer Networks Basic", type="learning", progress=42, whiteboard=[])
    t1 = models.Task(id="t1", workspace_id="ws1", project_id="p1", title="OSI Model", status="done", priority="medium", estimated_hours=1, resources=[])
    db.session.add_all([u1, ws1])
    db.session.commit()
    db.session.add(models.WorkspaceMember(workspace_id="ws1", user_id="u1", role_id="owner"))
    db.session.commit()
    db.session.add(c1)
    db.session.commit()
    db.session.add(p1)
    db.session.commit()
    db.session.add(t1)
    db.session.commit()

    if second_workspace:
        u2 = models.User(id="u2", email="u2@example.com", name="User Two")
        ws2 = models.Workspace(id="ws2", name="WS 2", context="personal", type="project", owner_id="u2")
        c2 = models.Company(id="c2", workspace_id="ws2", name="Other", mission="m", color="indigo", whiteboard=[])
        p2 = models.Project(id="p2", workspace_id="ws2", company_id="c2", name="Foreign Project", type="learning", progress=0, whiteboard=[])
        db.session.add_all([u2, ws2])
        db.session.commit()
        db.session.add(c2)
        db.session.commit()
        db.session.add(p2)
        db.session.commit()
    return u1


def _ctx(run_id="run-plan", project_id=None):
    return ExecutionContext(
        request_id=f"req-{run_id}",
        user_id="u1",
        workspace_id="ws1",
        session_id="s1",
        run_id=run_id,
        scope_level="project" if project_id else "workspace",
        scope_project_id=project_id,
    )


def _content():
    return {
        "title": "Intermediate Computer Networks",
        "description": "Create an 8-week intermediate Computer Networks plan.",
        "metadata": {"horizon_weeks": 8, "estimated_effort_hours": 8},
        "phases": [
            {
                "id": "phase-1",
                "title": "Transport Layer",
                "description": "TCP and UDP foundations",
                "sequence": 1,
                "tasks": [
                    {"id": "task-1", "title": "Study TCP flow control", "description": "Read and summarize", "estimated_hours": 2},
                    {"id": "task-2", "title": "Review transport layer", "description": "Validate retention", "estimated_hours": 1},
                ],
            }
        ],
    }


def test_plan_proposal_lifecycle_and_no_premature_mutation(db):
    _seed(db)
    ctx = _ctx("run-lifecycle", project_id="p1")
    with execution_context(ctx):
        proposal = create_plan_proposal(ctx, "Create an 8-week intermediate Computer Networks plan.", content=_content())

    assert proposal.status == PlanStatus.REVIEWING
    assert proposal.quality_status == QualityStatus.FAIL
    assert models.Milestone.query.count() == 0
    assert models.Task.query.count() == 1


def test_ready_plan_apply_and_idempotent_retry(db):
    _seed(db)
    ctx = _ctx("run-apply", project_id="p1")
    with execution_context(ctx):
        proposal = create_plan_proposal(ctx, "Create an 8-week intermediate Computer Networks plan.")
        first = apply_plan_proposal(proposal.id)
        second = apply_plan_proposal(proposal.id)

    assert first["data"]["status"] == PlanStatus.APPLIED
    assert second["data"]["status"] == PlanStatus.APPLIED
    assert models.Milestone.query.filter_by(project_id="p1").count() == proposal.content["metadata"]["horizon_weeks"] // 2
    assert models.AgentAction.query.filter(models.AgentAction.id.like(f"plan_{proposal.id}_v1_%")).count() > 0


def test_new_version_gets_distinct_actions(db):
    _seed(db)
    ctx = _ctx("run-version", project_id="p1")
    with execution_context(ctx):
        v1 = create_plan_proposal(ctx, "Create an 8-week intermediate Computer Networks plan.")
        apply_plan_proposal(v1.id)
        v2 = create_plan_proposal(ctx, "Create an 8-week intermediate Computer Networks plan.", supersedes_id=v1.id, revision_reason="more practice")
        apply_plan_proposal(v2.id)

    assert v2.version == 2
    assert models.AgentAction.query.filter(models.AgentAction.id.like(f"plan_{v1.id}_v1_%")).count() > 0
    assert models.AgentAction.query.filter(models.AgentAction.id.like(f"plan_{v2.id}_v2_%")).count() > 0


def test_partial_failure_marks_proposal_partially_applied(db):
    _seed(db)
    ctx = _ctx("run-partial-plan", project_id="p1")
    with execution_context(ctx):
        proposal = create_plan_proposal(ctx, "Create an 8-week intermediate Computer Networks plan.")
        result = apply_plan_proposal(proposal.id, fail_refs={"phase-1-task-1"})

    assert result["data"]["status"] == PlanStatus.PARTIALLY_APPLIED
    assert result["data"]["applicationResult"]["failures"] >= 1
    failed = models.AgentAction.query.filter_by(id=f"plan_{proposal.id}_v1_phase-1-task-1").one()
    assert failed.status == ActionStatus.FAILED.value


def test_plan_apply_blocks_cross_workspace_scope(db):
    _seed(db, second_workspace=True)
    ctx = _ctx("run-auth")
    bad_ctx = ExecutionContext(**{**ctx.__dict__, "scope_level": "project", "scope_project_id": "p2"})
    with execution_context(bad_ctx):
        proposal = create_plan_proposal(bad_ctx, "Create a plan for the foreign project.")
        result = apply_plan_proposal(proposal.id)

    assert result["success"] is False
    assert "Unauthorized" in result["error"]


def test_project_scope_context_includes_project_without_unrelated_projects(db):
    _seed(db)
    ctx = _ctx("run-scope", project_id="p1")
    envelope = build_context_envelope(ctx, [])
    assert envelope["scope"]["level"] == "project"
    assert envelope["scoped_entity"]["id"] == "p1"
    assert envelope["relevant_entities"]["projects"] == []
    assert {t["project_id"] for t in envelope["relevant_entities"]["tasks"]} == {"p1"}


def test_confirmation_records_action_without_execution(db):
    _seed(db)
    ctx = _ctx("run-confirm", project_id="p1")
    with execution_context(ctx):
        proposal = create_plan_proposal(ctx, "Create an 8-week intermediate Computer Networks plan.")
        result = request_plan_confirmation(proposal.id)

    assert result["success"] is True
    refreshed = models.PlanProposal.query.get(proposal.id)
    assert refreshed.status == PlanStatus.WAITING_FOR_CONFIRMATION
    parent = models.AgentAction.query.get(refreshed.applied_action_id)
    assert parent.status == ActionStatus.WAITING_FOR_CONFIRMATION.value
    assert models.Milestone.query.count() == 0


def test_chat_sse_emits_typed_plan_event(app, client, db):
    user = _seed(db)
    token = create_access_token(identity=user.id)
    session_resp = client.post(
        "/api/v1/chat/sessions",
        json={"workspace_id": "ws1", "scope_level": "project", "scope_project_id": "p1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    session_id = session_resp.get_json()["id"]

    resp = client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"workspace_id": "ws1", "content": "Create an 8-week intermediate Computer Networks plan."},
        headers={"Authorization": f"Bearer {token}"},
    )
    payloads = []
    for line in resp.get_data(as_text=True).splitlines():
        if line.startswith("data: "):
            payloads.append(json.loads(line[6:]))

    event_types = {payload["type"] for payload in payloads}
    assert "agent_run_started" in event_types
    assert "plan_proposed" in event_types
    assert "agent_run_completed" in event_types
    assert models.Milestone.query.count() == 0
