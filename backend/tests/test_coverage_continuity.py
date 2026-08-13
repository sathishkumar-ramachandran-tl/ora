from app import models
from app.agents.coverage import concept_key
from app.agents.execution_context import ExecutionContext, execution_context
from app.agents.planning import apply_plan_proposal, create_plan_proposal
from app.agents.planning_benchmark import run_computer_networks_benchmark


def _seed_workspace(db, suffix="1"):
    user = models.User(id=f"u{suffix}", email=f"u{suffix}@example.com", name=f"User {suffix}")
    ws = models.Workspace(id=f"ws{suffix}", name=f"WS {suffix}", context="personal", type="project", owner_id=user.id)
    company = models.Company(id=f"c{suffix}", workspace_id=ws.id, name=f"Initiative {suffix}", mission="m", color="indigo", whiteboard=[])
    project = models.Project(id=f"p{suffix}", workspace_id=ws.id, company_id=company.id, name="Computer Networks", type="learning", progress=0, whiteboard=[])
    db.session.add_all([user, ws])
    db.session.commit()
    db.session.add(models.WorkspaceMember(workspace_id=ws.id, user_id=user.id, role_id="owner"))
    db.session.commit()
    db.session.add(company)
    db.session.commit()
    db.session.add(project)
    db.session.commit()
    return user, ws, project


def _ctx(run_id="run-coverage", workspace_id="ws1", user_id="u1", project_id="p1"):
    return ExecutionContext(
        request_id=f"req-{run_id}",
        user_id=user_id,
        workspace_id=workspace_id,
        session_id="s1",
        run_id=run_id,
        scope_level="project",
        scope_project_id=project_id,
    )


def test_basic_exists_intermediate_retrieves_prior_coverage(db):
    _seed_workspace(db)
    with execution_context(_ctx("run-basic")):
        basic = create_plan_proposal(_ctx("run-basic"), "Create a beginner Computer Networks curriculum.")
        apply_plan_proposal(basic.id)

    with execution_context(_ctx("run-intermediate")):
        intermediate = create_plan_proposal(_ctx("run-intermediate"), "Create Intermediate Computer Networks.")

    context = intermediate.planning_context
    assert context["coverage_summary"]["total_concepts"] > 0
    decisions = {item["decision"] for item in context["coverage_analysis"]["classifications"]}
    assert "DEEPEN" in decisions
    assert context["plan_differential"]["deepens"]


def test_basic_and_intermediate_advanced_receives_both_coverage_sets(db):
    _seed_workspace(db)
    with execution_context(_ctx("run-sequence")):
        basic = create_plan_proposal(_ctx("run-sequence"), "Create a beginner Computer Networks curriculum.")
        apply_plan_proposal(basic.id)
        intermediate = create_plan_proposal(_ctx("run-sequence"), "Create Intermediate Computer Networks.")
        apply_plan_proposal(intermediate.id)
        advanced = create_plan_proposal(_ctx("run-sequence"), "Create an advanced top-university-level Computer Networks specialization.")

    context = advanced.planning_context
    depths = context["coverage_summary"]["by_depth"]
    assert depths["FOUNDATIONAL"] > 0
    assert depths["INTERMEDIATE"] > 0
    decisions = {item["decision"] for item in context["coverage_analysis"]["classifications"]}
    assert "ASSUME" in decisions
    assert "DEEPEN" in decisions


def test_duplicate_foundational_concept_is_not_recreated_as_new(db):
    _seed_workspace(db)
    with execution_context(_ctx("run-dupe")):
        basic = create_plan_proposal(_ctx("run-dupe"), "Create a beginner Computer Networks curriculum.")
        apply_plan_proposal(basic.id)
        intermediate = create_plan_proposal(_ctx("run-dupe"), "Create Intermediate Computer Networks.")

    subnetting = concept_key("subnetting", domain="computer_networks")
    diff = intermediate.content["differential"]
    assert subnetting not in {item["concept_key"] for item in diff["adds"]}
    assert subnetting in {item["concept_key"] for item in diff["deepens"]}


def test_existing_intermediate_concept_can_deepen_in_advanced_plan(db):
    _seed_workspace(db)
    with execution_context(_ctx("run-deepen")):
        intermediate = create_plan_proposal(_ctx("run-deepen"), "Create Intermediate Computer Networks.")
        apply_plan_proposal(intermediate.id)
        advanced = create_plan_proposal(_ctx("run-deepen"), "Create an advanced top-university-level Computer Networks specialization.")

    congestion = concept_key("tcp congestion control", domain="computer_networks")
    assert congestion in {item["concept_key"] for item in advanced.content["differential"]["deepens"]}


def test_quality_flags_missing_prerequisite_for_advanced_concept(db):
    _seed_workspace(db)
    content = {
        "title": "Advanced Networking",
        "description": "Advanced networking plan",
        "phases": [{
            "id": "phase-1",
            "title": "BGP Route Policy",
            "concepts": [{
                "key": concept_key("bgp route policy", domain="computer_networks"),
                "name": "BGP Route Policy",
                "domain": "computer_networks",
                "coverage": "INTRODUCES",
                "depth": "ADVANCED",
            }],
            "tasks": [{"id": "t1", "title": "Study BGP policy", "concepts": []}],
        }, {
            "id": "phase-2",
            "title": "Assessment",
            "tasks": [{"id": "t2", "title": "Review BGP policy", "concepts": []}],
        }],
    }
    with execution_context(_ctx("run-prereq")):
        proposal = create_plan_proposal(_ctx("run-prereq"), "Create advanced Computer Networks.", content=content)

    findings = proposal.quality_report["findings"]
    assert any(f["dimension"] == "prerequisite_correctness" and f["severity"] == "high" for f in findings)


def test_plan_revision_preserves_parent_and_reason(db):
    _seed_workspace(db)
    with execution_context(_ctx("run-revision")):
        v1 = create_plan_proposal(_ctx("run-revision"), "Create Intermediate Computer Networks.")
        v2 = create_plan_proposal(
            _ctx("run-revision"),
            "Create Intermediate Computer Networks.",
            supersedes_id=v1.id,
            revision_reason="User already knows subnetting.",
        )

    assert v2.version == 2
    assert v2.supersedes_id == v1.id
    assert v2.revision_reason == "User already knows subnetting."


def test_cross_workspace_coverage_is_never_injected(db):
    _seed_workspace(db, "1")
    _seed_workspace(db, "2")
    with execution_context(_ctx("run-ws2", "ws2", "u2", "p2")):
        other = create_plan_proposal(_ctx("run-ws2", "ws2", "u2", "p2"), "Create Intermediate Computer Networks.")
        apply_plan_proposal(other.id)

    with execution_context(_ctx("run-ws1", "ws1", "u1", "p1")):
        proposal = create_plan_proposal(_ctx("run-ws1", "ws1", "u1", "p1"), "Create Advanced Computer Networks.")

    assert proposal.planning_context["coverage_summary"]["total_concepts"] == 0
    assert not proposal.planning_context["coverage_records"]


def test_apply_creates_coverage_records_idempotently(db):
    _seed_workspace(db)
    with execution_context(_ctx("run-apply-coverage")):
        proposal = create_plan_proposal(_ctx("run-apply-coverage"), "Create Intermediate Computer Networks.")
        first = apply_plan_proposal(proposal.id)
        count_after_first = models.CoverageRecord.query.count()
        second = apply_plan_proposal(proposal.id)

    assert first["data"]["applicationResult"]["coverage_records"] == count_after_first
    assert second["data"]["applicationResult"]["coverage_records"] == count_after_first
    assert models.CoverageRecord.query.count() == count_after_first


def test_computer_networks_benchmark_reports_structured_results(db):
    _seed_workspace(db)
    results = run_computer_networks_benchmark(_ctx("run-benchmark"))
    assert [r["scenario"] for r in results] == ["A", "B", "C"]
    assert results[0]["prior_context_retrieved"] == 0
    assert results[1]["prior_context_retrieved"] > 0
    assert results[2]["prior_context_retrieved"] > results[1]["prior_context_retrieved"]
    assert results[2]["new_concepts_added"] > 0
