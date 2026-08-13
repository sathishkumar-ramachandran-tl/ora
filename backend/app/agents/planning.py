"""Structured PlanProposal services.

The planner may recommend content, but applying it always compiles into Action specs
and flows through ActionExecutor/domain authorization.
"""
from __future__ import annotations

import re
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from ..core.extensions import db
from ..tools import task_tools
from .action_executor import ensure_agent_run, execute_action
from .coverage import (
    classify_prior_coverage,
    concept_key,
    coverage_for_workspace,
    lazy_extract_coverage_from_tasks,
    create_coverage_records_for_plan,
    infer_domain,
    infer_requested_depth,
    normalize_label,
    summarize_coverage,
)
from .control_plane import ActionStatus, AgentRunStatus, ErrorClass
from .execution_context import ExecutionContext, get_execution_context
from .mastery import mastery_for_workspace, serialize_mastery
from .models import AgentAction, AgentRun, PlanProposal
from .research import (
    collect_live_research_evidence,
    interpret_rigor,
    research_needed,
    serialize_research_evidence,
    synthesize_evidence_requirements,
)
from .rubrics import evaluate_rubric, get_rubric


class PlanStatus:
    DRAFT = "DRAFT"
    REVIEWING = "REVIEWING"
    READY = "READY"
    WAITING_FOR_CONFIRMATION = "WAITING_FOR_CONFIRMATION"
    APPLYING = "APPLYING"
    APPLIED = "APPLIED"
    PARTIALLY_APPLIED = "PARTIALLY_APPLIED"
    FAILED = "FAILED"
    SUPERSEDED = "SUPERSEDED"


class QualityStatus:
    UNREVIEWED = "UNREVIEWED"
    # Quality-review status enum, not a password.
    PASS = "PASS"  # nosec B105
    WARNING = "WARNING"
    FAIL = "FAIL"


MAX_QUALITY_REVISION_ROUNDS = 2


@dataclass
class ActionSpec:
    action_type: str
    tool_name: str
    args: dict[str, Any]
    proposed_ref: str
    depends_on: Optional[str] = None


def _norm(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def should_create_plan_proposal(message: str) -> bool:
    text = message.lower()
    if any(term in text for term in ("week plan", "weeks", "roadmap", "curriculum", "preparation plan")):
        return True
    if "plan" in text and any(term in text for term in ("create", "build", "make", "design", "prepare")):
        return True
    return False


def build_planning_context(ctx: ExecutionContext, goal: str) -> dict:
    from .. import models as m

    domain = infer_domain(goal)
    requested_depth = infer_requested_depth(goal)
    goal_terms = [t for t in _norm(goal).split() if len(t) > 3]
    projects_query = m.Project.query.filter_by(workspace_id=ctx.workspace_id)
    if ctx.scope_project_id:
        projects_query = projects_query.filter_by(id=ctx.scope_project_id)
    projects = projects_query.all()

    related_projects = []
    for project in projects:
        score = sum(1 for term in goal_terms if term in _norm(project.name) or term in _norm(project.mission))
        if ctx.scope_project_id == project.id or score:
            related_projects.append({
                "id": project.id,
                "name": project.name,
                "mission": project.mission,
                "progress": project.progress,
                "reason": "current_scope" if ctx.scope_project_id == project.id else "goal_title_match",
            })

    if not related_projects:
        related_projects = [
            {"id": p.id, "name": p.name, "mission": p.mission, "progress": p.progress, "reason": "workspace_recent"}
            for p in projects[:5]
        ]

    project_ids = [p["id"] for p in related_projects]
    milestones = []
    tasks = []
    if project_ids:
        milestones = [
            {"id": ms.id, "project_id": ms.project_id, "title": ms.title, "status": ms.status, "order": ms.order}
            for ms in m.Milestone.query.filter(m.Milestone.project_id.in_(project_ids)).order_by(m.Milestone.order.asc()).all()
        ]
        tasks = [
            {"id": t.id, "project_id": t.project_id, "title": t.title, "status": t.status, "priority": t.priority}
            for t in m.Task.query.filter(m.Task.project_id.in_(project_ids)).limit(80).all()
        ]

    existing_plans = [
        {"id": p.id, "title": p.title, "version": p.version, "status": p.status, "quality_status": p.quality_status}
        for p in PlanProposal.query.filter_by(workspace_id=ctx.workspace_id)
        .order_by(PlanProposal.created_at.desc()).limit(10).all()
    ]

    records = coverage_for_workspace(ctx.workspace_id, domain=domain, project_ids=project_ids or None)
    if not records and tasks:
        records = lazy_extract_coverage_from_tasks(ctx.workspace_id, tasks, domain=domain)
    mastery_records = mastery_for_workspace(ctx, domain=domain)
    coverage_analysis = classify_prior_coverage(goal, records, mastery_records)
    rubric = get_rubric(domain)
    research_result = collect_live_research_evidence(ctx, goal, domain=domain)
    evidence = research_result.get("evidence") or []
    evidence_requirements = synthesize_evidence_requirements(evidence)
    research = {
        "needed": research_needed(goal, domain=domain),
        "status": research_result.get("status"),
        "queries": research_result.get("queries", []),
        "errors": research_result.get("errors", []),
        "evidence_count": len(evidence),
        "evidence": serialize_research_evidence(evidence),
        "requirements": evidence_requirements,
        "budget": {"max_sources": 5, "max_synthesis_rounds": 1},
    }
    rigor = interpret_rigor(goal)

    return {
        "goal": goal,
        "domain": domain,
        "requested_depth": requested_depth,
        "rubric": {"domain": rubric.domain, "dimensions": rubric.dimensions},
        "workspace": {"id": ctx.workspace_id},
        "scope": {
            "level": ctx.scope_level,
            "project_id": ctx.scope_project_id,
            "task_id": ctx.scope_task_id,
        },
        "related_projects": related_projects,
        "existing_milestones": milestones,
        "existing_tasks": tasks,
        "existing_plans": existing_plans,
        "coverage_records": [
            {
                "id": r.id,
                "project_id": r.project_id,
                "plan_proposal_id": r.plan_proposal_id,
                "concept_key": r.concept_key,
                "concept_name": r.concept_name,
                "coverage_type": r.coverage_type,
                "depth": r.depth,
                "status": r.status,
                "source_type": r.source_type,
                "source_id": r.source_id,
            }
            for r in records[:120]
        ],
        "coverage_summary": summarize_coverage(records),
        "coverage_analysis": coverage_analysis,
        "mastery_records": serialize_mastery(mastery_records),
        "weak_areas": [
            item for item in serialize_mastery(mastery_records)
            if item["status"] == "NEEDS_REVIEW"
        ],
        "research": research,
        "rigor": rigor,
        "plan_differential": build_plan_differential(coverage_analysis, requested_depth, domain, evidence_requirements),
        "constraints": _extract_constraints(goal),
        "relevant_knowledge": [],
    }


def build_plan_differential(
    coverage_analysis: dict,
    requested_depth: str,
    domain: str,
    evidence_requirements: list[dict] | None = None,
) -> dict:
    classifications = coverage_analysis.get("classifications", [])
    builds_on = [c for c in classifications if c["decision"] in {"ASSUME", "SKIP_DUPLICATE"}]
    deepens = [c for c in classifications if c["decision"] == "DEEPEN"]
    reviews = [c for c in classifications if c["decision"] == "REVIEW"]
    known = {c["concept_key"] for c in classifications}
    research_backed = [
        {**req, "decision": "ADD_NEW"}
        for req in evidence_requirements or []
        if req["concept_key"] not in known
    ]
    return {
        "requested_depth": requested_depth,
        "domain": domain,
        "builds_on": builds_on[:20],
        "deepens": deepens[:20],
        "reviews": reviews[:20],
        "skipped_as_duplicate": [c for c in classifications if c["decision"] == "SKIP_DUPLICATE"][:20],
        "adds": [],
        "research_backed": research_backed[:20],
    }


def _extract_constraints(goal: str) -> list[str]:
    constraints = []
    text = goal.lower()
    if "without moving" in text:
        constraints.append("Do not move fixed dates mentioned by the user.")
    match = re.search(r"(\d+)\s*[- ]?(week|weeks|month|months)", text)
    if match:
        constraints.append(f"Requested horizon: {match.group(0)}.")
    return constraints


def create_plan_proposal(
    ctx: ExecutionContext,
    goal: str,
    *,
    title: Optional[str] = None,
    content: Optional[dict] = None,
    supersedes_id: Optional[str] = None,
    revision_reason: Optional[str] = None,
) -> PlanProposal:
    run = ensure_agent_run(ctx)
    planning_context = build_planning_context(ctx, goal)
    version = 1
    if supersedes_id:
        previous = db.session.get(PlanProposal, supersedes_id)
        if previous and previous.workspace_id == ctx.workspace_id:
            previous.status = PlanStatus.SUPERSEDED
            version = (previous.version or 1) + 1

    plan_content = content or _draft_generic_plan(goal, title, planning_context)
    plan_content = annotate_plan_semantics(plan_content, planning_context)
    plan_content["differential"] = update_differential_with_plan(
        planning_context.get("plan_differential", {}),
        plan_content,
        planning_context.get("domain") or infer_domain(goal),
    )
    duplication_report = analyze_duplication(plan_content, planning_context)
    quality_report = evaluate_plan_quality(plan_content, planning_context, duplication_report)
    revision_count = 0
    if content is None:
        while quality_report["status"] == QualityStatus.FAIL and revision_count < MAX_QUALITY_REVISION_ROUNDS:
            revised = revise_plan_for_quality(plan_content, quality_report, planning_context)
            if revised == plan_content:
                break
            plan_content = revised
            plan_content = annotate_plan_semantics(plan_content, planning_context)
            plan_content["differential"] = update_differential_with_plan(
                planning_context.get("plan_differential", {}),
                plan_content,
                planning_context.get("domain") or infer_domain(goal),
            )
            duplication_report = analyze_duplication(plan_content, planning_context)
            quality_report = evaluate_plan_quality(plan_content, planning_context, duplication_report)
            revision_count += 1
        plan_content.setdefault("metadata", {})["quality_revision_count"] = revision_count
    status = PlanStatus.READY if quality_report["status"] in {QualityStatus.PASS, QualityStatus.WARNING} else PlanStatus.REVIEWING

    proposal = PlanProposal(
        id=str(uuid.uuid4()),
        run_id=run.id,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        scope_level=ctx.scope_level,
        scope_project_id=ctx.scope_project_id,
        scope_task_id=ctx.scope_task_id,
        title=title or plan_content.get("title") or _title_from_goal(goal),
        goal=goal,
        status=status,
        version=version,
        quality_status=quality_report["status"],
        supersedes_id=supersedes_id,
        revision_reason=revision_reason,
        content=plan_content,
        planning_context=planning_context,
        duplication_report=duplication_report,
        quality_report=quality_report,
    )
    db.session.add(proposal)
    db.session.commit()
    return proposal


def _title_from_goal(goal: str) -> str:
    clean = re.sub(r"\s+", " ", goal).strip().rstrip(".")
    clean = re.sub(r"^(create|build|make|design)\s+", "", clean, flags=re.I)
    return clean[:90] or "Plan Proposal"


def _draft_generic_plan(goal: str, title: Optional[str], planning_context: dict) -> dict:
    horizon = re.search(r"(\d+)\s*[- ]?weeks?", goal.lower())
    weeks = int(horizon.group(1)) if horizon else 4
    domain = planning_context.get("domain") or infer_domain(goal)
    requested_depth = planning_context.get("requested_depth") or infer_requested_depth(goal)
    plan_title = title or _title_from_goal(goal)
    concept_specs = _select_plan_concepts(plan_title, requested_depth, planning_context)
    milestone_count = min(6, max(3, min(len(concept_specs), weeks // 2 if weeks else 3)))
    phases = []
    for i in range(milestone_count):
        phase_num = i + 1
        spec = concept_specs[i % len(concept_specs)]
        concept = {
            "key": spec["key"],
            "name": spec["name"],
            "domain": domain,
            "coverage": spec["coverage"],
            "depth": spec["depth"],
            "prerequisites": [
                {"key": concept_key(p, domain=domain), "name": p}
                for p in spec.get("prerequisites", [])
            ],
            "source_ids": spec.get("source_ids", []),
            "rationale": spec.get("rationale", []),
        }
        phases.append({
            "id": f"phase-{phase_num}",
            "title": spec["name"],
            "description": f"{spec['coverage'].title().replace('_', ' ')} {spec['name']} at {spec['depth'].lower()} depth.",
            "sequence": phase_num,
            "target": f"Week {min(weeks, max(1, phase_num * max(1, weeks // milestone_count)))}",
            "concepts": [concept],
            "prerequisites": concept["prerequisites"],
            "expected_outcomes": [f"Clear evidence applying {spec['name']} in the context of {plan_title}."],
            "tasks": [
                {
                    "id": f"phase-{phase_num}-task-1",
                    "title": f"Study {spec['name']}",
                    "description": "Use existing materials and notes; summarize key ideas.",
                    "sequence": 1,
                    "estimated_hours": 3,
                    "priority": "high" if phase_num == 1 else "medium",
                    "dependencies": [],
                    "concepts": [{**concept, "coverage": "INTRODUCES" if spec["coverage"] == "ADD_NEW" else spec["coverage"]}],
                    "learning_objective": f"Explain and reason about {spec['name']}.",
                    "evidence_objective": "Short notes or worked examples.",
                    "concept_refs": [spec["key"]],
                    "prerequisite_refs": [p["key"] for p in concept["prerequisites"]],
                    "coverage_refs": [],
                },
                {
                    "id": f"phase-{phase_num}-task-2",
                    "title": f"Apply {spec['name']} in practice",
                    "description": "Turn the concepts into exercises, examples, or implementation notes.",
                    "sequence": 2,
                    "estimated_hours": 2,
                    "priority": "medium",
                    "dependencies": [f"phase-{phase_num}-task-1"],
                    "concepts": [{**concept, "coverage": "PRACTICES"}],
                    "learning_objective": f"Use {spec['name']} to solve applied problems.",
                    "evidence_objective": "Completed exercises, lab notes, or implementation artifact.",
                    "concept_refs": [spec["key"]],
                    "prerequisite_refs": [f"phase-{phase_num}-task-1"],
                    "coverage_refs": [],
                },
                {
                    "id": f"phase-{phase_num}-task-3",
                    "title": f"Review and assess {spec['name']}",
                    "description": "Check retention, identify gaps, and update the next phase if needed.",
                    "sequence": 3,
                    "estimated_hours": 1,
                    "priority": "medium",
                    "dependencies": [f"phase-{phase_num}-task-2"],
                    "concepts": [{**concept, "coverage": "ASSESSES"}],
                    "learning_objective": f"Validate readiness to build on {spec['name']}.",
                    "evidence_objective": "Self-test, review notes, or scored assessment.",
                    "concept_refs": [spec["key"]],
                    "prerequisite_refs": [f"phase-{phase_num}-task-2"],
                    "coverage_refs": [],
                },
            ],
        })
    return {
        "title": plan_title,
        "description": goal,
        "metadata": {"horizon_weeks": weeks, "estimated_effort_hours": milestone_count * 6},
        "phases": phases,
    }


def _select_plan_concepts(plan_title: str, requested_depth: str, planning_context: dict) -> list[dict]:
    domain = planning_context.get("domain") or infer_domain(plan_title)
    rubric = get_rubric(domain)
    depth_map = rubric.expected_by_depth or {}
    depth_names = depth_map.get(requested_depth) or [plan_title]
    classifications = {
        item["concept_key"]: item
        for item in (planning_context.get("coverage_analysis") or {}).get("classifications", [])
    }
    research_requirements = {
        req["concept_key"]: req
        for req in ((planning_context.get("research") or {}).get("requirements") or [])
    }
    research_names = [
        req["concept_name"]
        for req in research_requirements.values()
        if req["concept_key"] not in {concept_key(name, domain=domain) for name in depth_names}
    ]
    depth_names = depth_names + research_names

    current_depth_specs = []
    for name in depth_names:
        key = concept_key(name, domain=domain)
        prior = classifications.get(key)
        if prior and prior["decision"] == "SKIP_DUPLICATE":
            continue
        evidence_req = research_requirements.get(key)
        coverage = "DEEPENS" if prior and prior["decision"] == "DEEPEN" else "REVIEWS" if prior and prior["decision"] == "REVIEW" else "INTRODUCES"
        current_depth_specs.append({
            "key": key,
            "name": name.title(),
            "coverage": coverage,
            "depth": requested_depth,
            "prerequisites": (rubric.prerequisites or {}).get(name, []),
            "source_ids": (evidence_req or {}).get("source_ids", []),
            "rationale": (evidence_req or {}).get("rationale", []),
        })

    prior_deepen_specs = []
    current_keys = {s["key"] for s in current_depth_specs}
    for prior in classifications.values():
        if prior["decision"] == "DEEPEN" and prior["concept_key"] not in current_keys:
            prior_deepen_specs.append({
                "key": prior["concept_key"],
                "name": prior["concept_name"],
            "coverage": "DEEPENS",
            "depth": requested_depth,
            "prerequisites": [],
            "source_ids": [],
            "rationale": [],
        })
    prior_deepen_specs = sorted(
        prior_deepen_specs,
        key=lambda item: (0 if "subnet" in item["key"] else 1, item["key"]),
    )
    specs = _add_missing_prerequisite_specs(
        prior_deepen_specs[:1] + current_depth_specs + prior_deepen_specs[1:],
        classifications,
        domain,
        rubric.prerequisites or {},
        requested_depth,
    )
    return specs or [{
        "key": concept_key(plan_title, domain=domain),
        "name": plan_title,
        "coverage": "INTRODUCES",
        "depth": requested_depth,
        "prerequisites": [],
    }]


def _add_missing_prerequisite_specs(
    specs: list[dict],
    classifications: dict[str, dict],
    domain: str,
    prerequisites: dict[str, list[str]],
    requested_depth: str,
) -> list[dict]:
    available = {
        key
        for key, item in classifications.items()
        if item.get("decision") in {"ASSUME", "DEEPEN", "SKIP_DUPLICATE"}
    } | {spec["key"] for spec in specs}
    inserted: list[dict] = []
    inserted_keys = set()
    for spec in specs:
        prereq_names = prerequisites.get(spec["name"].lower()) or prerequisites.get(spec["name"]) or spec.get("prerequisites") or []
        for prereq in prereq_names:
            key = concept_key(prereq, domain=domain)
            if key in available or key in inserted_keys:
                continue
            inserted.append({
                "key": key,
                "name": prereq.title(),
                "coverage": "REVIEWS",
                "depth": "INTERMEDIATE" if requested_depth == "ADVANCED" else "FOUNDATIONAL",
                "prerequisites": [],
                "source_ids": spec.get("source_ids", []),
                "rationale": [f"Prerequisite repair for {spec['name']}."],
            })
            inserted_keys.add(key)
            available.add(key)
    return inserted + specs


def annotate_plan_semantics(content: dict, planning_context: dict) -> dict:
    domain = planning_context.get("domain") or infer_domain(f"{content.get('title')} {content.get('description')}")
    depth = planning_context.get("requested_depth") or infer_requested_depth(content.get("description"))
    for phase in content.get("phases", []):
        if not phase.get("concepts"):
            name = phase.get("title") or content.get("title")
            phase["concepts"] = [{
                "key": concept_key(name, domain=domain),
                "name": name,
                "domain": domain,
                "coverage": "INTRODUCES",
                "depth": depth,
                "prerequisites": phase.get("prerequisites", []),
            }]
        for task in phase.get("tasks", []):
            if not task.get("concepts"):
                task["concepts"] = phase.get("concepts", [])
            task.setdefault("learning_objective", f"Make progress on {task.get('title')}")
            task.setdefault("evidence_objective", "Concrete notes, exercise output, or review artifact.")
    return content


def update_differential_with_plan(differential: dict, content: dict, domain: str) -> dict:
    existing_keys = {
        item["concept_key"]
        for bucket in ("builds_on", "deepens", "reviews", "skipped_as_duplicate")
        for item in differential.get(bucket, [])
    }
    added = []
    deepens = list(differential.get("deepens", []))
    reviews = list(differential.get("reviews", []))
    for phase in content.get("phases", []):
        for concept in phase.get("concepts", []):
            key = concept.get("key") or concept_key(concept.get("name"), domain=domain)
            item = {
                "concept_key": key,
                "concept_name": concept.get("name") or key,
                "depth": concept.get("depth"),
                "coverage": concept.get("coverage"),
            }
            if concept.get("coverage") == "DEEPENS" and key not in {d["concept_key"] for d in deepens}:
                deepens.append({**item, "decision": "DEEPEN"})
            elif concept.get("coverage") == "REVIEWS" and key not in {r["concept_key"] for r in reviews}:
                reviews.append({**item, "decision": "REVIEW"})
            elif key not in existing_keys:
                added.append({**item, "decision": "ADD_NEW"})
    return {**differential, "deepens": deepens, "reviews": reviews, "adds": added}


def revise_plan_for_quality(content: dict, quality_report: dict, planning_context: dict) -> dict:
    revised = {
        **content,
        "metadata": dict(content.get("metadata") or {}),
        "phases": [dict(phase) for phase in content.get("phases", [])],
    }
    domain = planning_context.get("domain") or infer_domain(content.get("title"))
    depth = planning_context.get("requested_depth") or infer_requested_depth(content.get("description"))
    existing_phase_ids = {phase.get("id") for phase in revised["phases"]}
    existing_keys = {
        concept.get("key")
        for phase in revised["phases"]
        for concept in phase.get("concepts", [])
    }
    changed = False
    for finding in quality_report.get("findings", []):
        evidence = finding.get("evidence") or {}
        repair_keys = list(evidence.get("missing_prerequisites", []) or []) + list(evidence.get("missing_concepts", []) or [])
        for key in repair_keys[:3]:
            if key in existing_keys:
                continue
            name = key.split(".")[-1].replace("_", " ").title()
            phase_id = f"quality-add-{key.replace('.', '-')}"
            if phase_id in existing_phase_ids:
                continue
            concept = {
                "key": key,
                "name": name,
                "domain": domain,
                "coverage": "REVIEWS" if finding.get("dimension") == "prerequisite_correctness" else "INTRODUCES",
                "depth": "INTERMEDIATE" if finding.get("dimension") == "prerequisite_correctness" and depth == "ADVANCED" else depth,
                "prerequisites": [],
                "source_ids": evidence.get("source_ids", []),
                "rationale": [finding.get("message")],
            }
            revised["phases"].append({
                "id": phase_id,
                "title": name,
                "description": f"Added during bounded quality revision for {finding.get('dimension')}.",
                "sequence": len(revised["phases"]) + 1,
                "concepts": [concept],
                "tasks": [
                    {
                        "id": f"{phase_id}-study",
                        "title": f"Study {name}",
                        "description": "Address quality gap identified by the planning rubric.",
                        "estimated_hours": 2,
                        "priority": "medium",
                        "concepts": [concept],
                        "learning_objective": f"Understand {name}.",
                        "evidence_objective": "Notes, applied exercise, or review artifact.",
                    },
                    {
                        "id": f"{phase_id}-review",
                        "title": f"Review and validate {name}",
                        "description": "Check retention and application readiness.",
                        "estimated_hours": 1,
                        "priority": "medium",
                        "concepts": [{**concept, "coverage": "ASSESSES"}],
                        "learning_objective": f"Validate readiness for {name}.",
                        "evidence_objective": "Self-test or assessment artifact.",
                    },
                ],
            })
            existing_keys.add(key)
            existing_phase_ids.add(phase_id)
            changed = True
    if changed:
        revised["metadata"]["estimated_effort_hours"] = sum(
            task.get("estimated_hours", 1)
            for phase in revised["phases"]
            for task in phase.get("tasks", [])
        )
    return revised if changed else content


def analyze_duplication(content: dict, planning_context: dict) -> dict:
    existing_titles = {_norm(t["title"]): t for t in planning_context.get("existing_tasks", [])}
    existing_milestones = {_norm(m["title"]): m for m in planning_context.get("existing_milestones", [])}
    prior_decisions = {
        item["concept_key"]: item["decision"]
        for item in (planning_context.get("coverage_analysis") or {}).get("classifications", [])
    }
    findings = []
    for phase in content.get("phases", []):
        phase_norm = _norm(phase.get("title"))
        classification = "POSSIBLE_DUPLICATE" if phase_norm in existing_milestones else "NEW"
        findings.append({"kind": "milestone", "title": phase.get("title"), "classification": classification})
        for concept in phase.get("concepts", []):
            key = concept.get("key")
            if prior_decisions.get(key) == "SKIP_DUPLICATE" and concept.get("coverage") in {"INTRODUCES", "PRACTICES"}:
                findings.append({
                    "kind": "concept",
                    "title": concept.get("name") or key,
                    "concept_key": key,
                    "classification": "POSSIBLE_DUPLICATE",
                    "evidence": {"prior_decision": "SKIP_DUPLICATE"},
                })
        for task in phase.get("tasks", []):
            task_norm = _norm(task.get("title"))
            classification = "POSSIBLE_DUPLICATE" if task_norm in existing_titles else "NEW"
            findings.append({"kind": "task", "title": task.get("title"), "classification": classification})
    return {"findings": findings}


def evaluate_plan_quality(content: dict, planning_context: dict, duplication_report: Optional[dict] = None) -> dict:
    findings = []
    phases = content.get("phases", [])
    tasks = [task for phase in phases for task in phase.get("tasks", [])]
    if not content.get("title") or not content.get("description"):
        findings.append({"dimension": "goal_coverage", "severity": "high", "message": "Plan needs a title and goal description."})
    if len(phases) < 2:
        findings.append({"dimension": "logical_progression", "severity": "high", "message": "Plan should have multiple ordered phases."})
    if not tasks:
        findings.append({"dimension": "actionability", "severity": "high", "message": "Plan has no actionable tasks."})
    if not any("review" in _norm(t.get("title")) or "validate" in _norm(t.get("title")) for t in tasks):
        findings.append({"dimension": "assessment_or_validation", "severity": "medium", "message": "Plan should include review or validation work."})
    title_counts = Counter(_norm(t.get("title")) for t in tasks)
    duplicates = [title for title, count in title_counts.items() if title and count > 1]
    if duplicates:
        findings.append({"dimension": "redundancy", "severity": "medium", "message": "Plan repeats task titles internally."})
    for item in (duplication_report or {}).get("findings", []):
        if item.get("classification") == "POSSIBLE_DUPLICATE":
            findings.append({
                "dimension": "redundancy",
                "severity": "medium",
                "message": f"Possible duplicate {item.get('kind')}: {item.get('title')}",
                "evidence": item.get("evidence") or {"item": item},
            })
            break
    findings.extend(evaluate_rubric(content, planning_context))
    if planning_context.get("coverage_records") and not (content.get("differential") or {}).get("builds_on"):
        findings.append({
            "dimension": "continuity_with_prior_work",
            "severity": "medium",
            "message": "Plan has prior coverage available but does not explain what it builds on.",
            "evidence": {"coverage_record_count": len(planning_context.get("coverage_records") or [])},
        })

    if any(f["severity"] == "high" for f in findings):
        status = QualityStatus.FAIL
    elif findings:
        status = QualityStatus.WARNING
    else:
        status = QualityStatus.PASS
    return {"status": status, "findings": findings}


def compile_plan(proposal: PlanProposal) -> list[ActionSpec]:
    content = proposal.content or {}
    specs: list[ActionSpec] = []
    project_ref = "project"
    if proposal.scope_project_id:
        project_id = proposal.scope_project_id
    else:
        project_id = None
        specs.append(ActionSpec(
            action_type="project.create",
            tool_name="create_project",
            proposed_ref=project_ref,
            args={
                "name": content.get("title") or proposal.title,
                "project_type": "learning",
                "mission": proposal.goal or content.get("description") or "",
            },
        ))

    for phase in content.get("phases", []):
        phase_ref = phase.get("id") or f"phase-{len(specs)}"
        specs.append(ActionSpec(
            action_type="milestone.create",
            tool_name="create_milestone",
            proposed_ref=phase_ref,
            depends_on=project_ref if not project_id else None,
            args={
                "project_id": project_id,
                "title": phase.get("title") or "Milestone",
                "description": phase.get("description") or phase.get("target") or "",
                "order": phase.get("sequence", 0),
            },
        ))
        for task in phase.get("tasks", []):
            specs.append(ActionSpec(
                action_type="task.create",
                tool_name="create_task",
                proposed_ref=task.get("id") or str(uuid.uuid4()),
                depends_on=phase_ref,
                args={
                    "project_id": project_id,
                    "workspace_id": proposal.workspace_id,
                    "title": task.get("title") or "Untitled Task",
                    "description": task.get("description") or "",
                    "priority": task.get("priority") or "medium",
                    "estimated_hours": task.get("estimated_hours") or 1.0,
                    "status": "todo",
                },
            ))
    return specs


def request_plan_confirmation(proposal_id: str) -> dict:
    ctx = get_execution_context(required=True)
    proposal = db.session.get(PlanProposal, proposal_id)
    error = _validate_proposal_access(ctx, proposal)
    if error:
        return {"success": False, "data": None, "error": error}

    action = _ensure_parent_apply_action(ctx, proposal)
    action.status = ActionStatus.WAITING_FOR_CONFIRMATION.value
    proposal.status = PlanStatus.WAITING_FOR_CONFIRMATION
    proposal.applied_action_id = action.id
    db.session.commit()
    return {"success": True, "data": serialize_plan(proposal), "error": None}


def apply_plan_proposal(proposal_id: str, *, approved: bool = True, fail_refs: Optional[set[str]] = None) -> dict:
    ctx = get_execution_context(required=True)
    proposal = db.session.get(PlanProposal, proposal_id)
    error = _validate_proposal_access(ctx, proposal)
    if error:
        return {"success": False, "data": None, "error": error}
    if not approved:
        return request_plan_confirmation(proposal_id)

    parent = _ensure_parent_apply_action(ctx, proposal)
    parent.status = ActionStatus.APPROVED.value
    proposal.status = PlanStatus.APPLYING
    proposal.applied_action_id = parent.id
    db.session.commit()

    specs = compile_plan(proposal)
    compiled = []
    ref_results: dict[str, dict[str, Any]] = {}
    successes = failures = unknown = skipped = 0
    initiative_id = _default_initiative_id(ctx.workspace_id)

    for spec in specs:
        args = dict(spec.args)
        if spec.action_type == "project.create":
            if not initiative_id:
                failures += 1
                compiled.append(_compiled_record(spec, None, "FAILED", "No initiative exists in this workspace"))
                continue
            args["initiative_id"] = initiative_id
        if spec.depends_on:
            dep_result = ref_results.get(spec.depends_on)
            if not dep_result or not dep_result.get("resource_id"):
                skipped += 1
                compiled.append(_compiled_record(spec, None, "SKIPPED", "Dependency action did not produce a resource"))
                continue
            if spec.action_type == "milestone.create":
                args["project_id"] = dep_result["resource_id"]
            elif spec.action_type == "task.create":
                if spec.depends_on.startswith("phase"):
                    args["milestone_id"] = dep_result["resource_id"]
                    project_ref = ref_results.get("project")
                    if project_ref:
                        args["project_id"] = project_ref["resource_id"]
                else:
                    args["project_id"] = dep_result["resource_id"]

        action_id = f"plan_{proposal.id}_v{proposal.version}_{spec.proposed_ref}"
        result = execute_action(
            spec.action_type,
            spec.tool_name,
            args,
            lambda spec=spec, args=args: _invoke_spec(spec, args, fail_refs or set()),
            action_id=action_id,
            parent_action_id=parent.id,
        )
        action = db.session.get(AgentAction, action_id)
        status = action.status if action else "UNKNOWN"
        resource_id = action.resource_id if action else None
        if status == ActionStatus.SUCCEEDED.value:
            successes += 1
        elif status == ActionStatus.UNKNOWN.value:
            unknown += 1
        else:
            failures += 1
        ref_results[spec.proposed_ref] = {"resource_id": resource_id, "status": status, "result": result}
        compiled.append(_compiled_record(spec, action_id, status, result.get("error"), resource_id))

    parent.after_state = {"result": {"successes": successes, "failures": failures, "unknown": unknown, "skipped": skipped}}
    parent.status = ActionStatus.SUCCEEDED.value if failures == 0 and unknown == 0 and skipped == 0 else ActionStatus.FAILED.value
    parent.completed_at = datetime.utcnow()
    applied_project_id = proposal.scope_project_id or (ref_results.get("project") or {}).get("resource_id")
    coverage_records = create_coverage_records_for_plan(proposal, project_id=applied_project_id)
    proposal.compiled_actions = compiled
    proposal.application_result = {
        "successes": successes,
        "failures": failures,
        "unknown": unknown,
        "skipped": skipped,
        "coverage_records": len(coverage_records),
    }
    proposal.status = PlanStatus.APPLIED if failures == 0 and unknown == 0 and skipped == 0 else PlanStatus.PARTIALLY_APPLIED
    proposal.applied_at = datetime.utcnow()

    run = db.session.get(AgentRun, parent.run_id)
    if run:
        run.status = AgentRunStatus.COMPLETED.value if proposal.status == PlanStatus.APPLIED else AgentRunStatus.PARTIALLY_COMPLETED.value
        run.completed_at = datetime.utcnow()

    db.session.commit()
    return {"success": proposal.status == PlanStatus.APPLIED, "data": serialize_plan(proposal), "error": None}


def _validate_proposal_access(ctx: ExecutionContext, proposal: Optional[PlanProposal]) -> Optional[str]:
    if not proposal:
        return "PlanProposal not found"
    if proposal.workspace_id != ctx.workspace_id:
        return "Unauthorized: plan is outside the trusted workspace"
    from ..tools.task_tools import require_workspace_access, require_project_access
    error = require_workspace_access(ctx, proposal.workspace_id)
    if error:
        return error
    if proposal.scope_project_id:
        _, error = require_project_access(ctx, proposal.scope_project_id)
        if error:
            return error
    return None


def _ensure_parent_apply_action(ctx: ExecutionContext, proposal: PlanProposal) -> AgentAction:
    run = ensure_agent_run(ctx)
    action_id = f"plan_apply_{proposal.id}_v{proposal.version}"
    action = db.session.get(AgentAction, action_id)
    if action:
        return action
    action = AgentAction(
        id=action_id,
        run_id=run.id,
        action_type="plan.apply",
        resource_type="plan",
        resource_id=proposal.id,
        status=ActionStatus.PROPOSED.value,
        risk_level="HIGH",
        confirmation_required=True,
        idempotency_key=f"act_{action_id}",
        proposed_args={"proposal_id": proposal.id, "version": proposal.version},
    )
    db.session.add(action)
    db.session.commit()
    return action


def _default_initiative_id(workspace_id: str) -> Optional[str]:
    from .. import models as m
    initiative = m.Company.query.filter_by(workspace_id=workspace_id).order_by(m.Company.id.asc()).first()
    return initiative.id if initiative else None


def _invoke_spec(spec: ActionSpec, args: dict[str, Any], fail_refs: set[str]) -> dict:
    if spec.proposed_ref in fail_refs:
        return {"success": False, "data": None, "error": "Validation error: forced test failure"}
    if spec.action_type == "project.create":
        return task_tools.create_project(
            args["initiative_id"],
            get_execution_context().workspace_id,
            args["name"],
            args.get("project_type", "learning"),
            args.get("mission", ""),
        )
    if spec.action_type == "milestone.create":
        return task_tools.create_milestone(
            args["project_id"],
            args["title"],
            args.get("description", ""),
            args.get("due_date"),
            args.get("order", 0),
        )
    if spec.action_type == "task.create":
        result = task_tools.create_task(
            args["project_id"],
            args["workspace_id"],
            args["title"],
            args.get("description", ""),
            args.get("priority", "medium"),
            args.get("estimated_hours", 1.0),
            args.get("status", "todo"),
        )
        if result["success"] and args.get("milestone_id"):
            from .. import models as m
            task = db.session.get(m.Task, result["data"]["id"])
            if task:
                task.milestone_id = args["milestone_id"]
                db.session.commit()
        return result
    return {"success": False, "data": None, "error": f"Unsupported plan action {spec.action_type}"}


def _compiled_record(spec: ActionSpec, action_id: Optional[str], status: str, error: Optional[str] = None, resource_id: Optional[str] = None) -> dict:
    return {
        "action_id": action_id,
        "action_type": spec.action_type,
        "tool_name": spec.tool_name,
        "proposed_ref": spec.proposed_ref,
        "status": status,
        "resource_id": resource_id,
        "error": error,
    }


def serialize_plan(proposal: PlanProposal) -> dict:
    content = proposal.content or {}
    phases = content.get("phases", [])
    task_count = sum(len(p.get("tasks", [])) for p in phases)
    return {
        "id": proposal.id,
        "runId": proposal.run_id,
        "workspaceId": proposal.workspace_id,
        "scope": {
            "level": proposal.scope_level,
            "projectId": proposal.scope_project_id,
            "taskId": proposal.scope_task_id,
        },
        "title": proposal.title,
        "goal": proposal.goal,
        "status": proposal.status,
        "version": proposal.version,
        "qualityStatus": proposal.quality_status,
        "summary": {
            "phaseCount": len(phases),
            "taskCount": task_count,
            "estimatedEffortHours": (content.get("metadata") or {}).get("estimated_effort_hours"),
        },
        "content": content,
        "planningContext": proposal.planning_context or {},
        "qualityReport": proposal.quality_report or {},
        "duplicationReport": proposal.duplication_report or {},
        "compiledActions": proposal.compiled_actions or [],
        "applicationResult": proposal.application_result or {},
        "appliedActionId": proposal.applied_action_id,
        "createdAt": proposal.created_at.isoformat() if proposal.created_at else None,
        "updatedAt": proposal.updated_at.isoformat() if proposal.updated_at else None,
        "appliedAt": proposal.applied_at.isoformat() if proposal.applied_at else None,
    }
