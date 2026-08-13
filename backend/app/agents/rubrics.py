"""Planning quality rubrics.

Shared planner, domain-specific evaluation criteria. These are not separate agents.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .coverage import concept_key, infer_domain, infer_requested_depth, normalize_label


@dataclass(frozen=True)
class PlanningRubric:
    domain: str
    dimensions: list[str]
    expected_by_depth: dict[str, list[str]] = field(default_factory=dict)
    prerequisites: dict[str, list[str]] = field(default_factory=dict)
    practical_requirements: list[str] = field(default_factory=list)


GENERIC_RUBRIC = PlanningRubric(
    domain="general",
    dimensions=[
        "goal_coverage", "prerequisite_correctness", "progression", "depth",
        "actionability", "assessment_validation", "practical_application",
        "redundancy", "workload_realism", "internal_consistency",
        "continuity_with_prior_work",
    ],
    practical_requirements=["review", "practice", "validate"],
)


COMPUTER_NETWORKS_RUBRIC = PlanningRubric(
    domain="computer_networks",
    dimensions=[
        "goal_coverage", "prerequisite_correctness", "progression", "depth",
        "actionability", "assessment_validation", "practical_application",
        "redundancy", "workload_realism", "internal_consistency",
        "continuity_with_prior_work",
    ],
    expected_by_depth={
        "FOUNDATIONAL": [
            "osi model", "ipv4 addressing", "subnetting", "tcp handshake", "dns fundamentals",
        ],
        "INTERMEDIATE": [
            "tcp flow control", "tcp congestion control", "routing fundamentals",
            "queueing fundamentals", "network troubleshooting",
        ],
        "ADVANCED": [
            "bgp route policy", "network measurement", "datacenter networking",
            "software defined networking", "network security", "congestion performance",
        ],
    },
    prerequisites={
        "bgp route policy": ["routing fundamentals"],
        "datacenter networking": ["routing fundamentals", "tcp congestion control"],
        "network measurement": ["tcp congestion control"],
        "software defined networking": ["routing fundamentals"],
        "congestion performance": ["tcp congestion control", "queueing fundamentals"],
    },
    practical_requirements=["lab", "project", "measurement", "assessment", "review"],
)


EXAM_PREP_RUBRIC = PlanningRubric(
    domain="exam_preparation",
    dimensions=[
        "syllabus_coverage", "revision", "mock_testing", "time_allocation",
        "weak_area_remediation", "continuity_with_prior_work",
    ],
    practical_requirements=["revision", "mock", "assessment", "review"],
)


PRODUCT_MVP_RUBRIC = PlanningRubric(
    domain="product_mvp",
    dimensions=[
        "problem_validation", "scope_discipline", "technical_dependency",
        "launch_readiness", "feedback_loop", "risk_coverage",
    ],
    practical_requirements=["validation", "launch", "feedback", "risk"],
)


def get_rubric(goal_or_domain: str | None) -> PlanningRubric:
    domain = goal_or_domain if goal_or_domain in {
        "computer_networks", "exam_preparation", "product_mvp", "general"
    } else infer_domain(goal_or_domain)
    if domain == "computer_networks":
        return COMPUTER_NETWORKS_RUBRIC
    if domain == "exam_preparation":
        return EXAM_PREP_RUBRIC
    if domain == "product_mvp":
        return PRODUCT_MVP_RUBRIC
    return GENERIC_RUBRIC


def expected_concept_keys(rubric: PlanningRubric, depth: str) -> set[str]:
    depths = ["FOUNDATIONAL", "INTERMEDIATE", "ADVANCED"]
    max_index = depths.index(depth) if depth in depths else 0
    concepts: set[str] = set()
    for d in depths[:max_index + 1]:
        concepts.update(concept_key(name, domain=rubric.domain) for name in rubric.expected_by_depth.get(d, []))
    return concepts


def evaluate_rubric(content: dict, planning_context: dict) -> list[dict[str, Any]]:
    domain = planning_context.get("domain") or infer_domain(f"{content.get('title')} {content.get('description')}")
    rubric = get_rubric(domain)
    depth = planning_context.get("requested_depth") or infer_requested_depth(content.get("description"))
    plan_concepts = _plan_concept_keys(content, domain)
    findings: list[dict[str, Any]] = []

    expected_current_depth = {
        concept_key(name, domain=rubric.domain)
        for name in rubric.expected_by_depth.get(depth, [])
    }
    research_requirements = (planning_context.get("research") or {}).get("requirements") or []
    research_expected = {req["concept_key"] for req in research_requirements if req.get("domain") == domain}
    expected_current_depth.update(research_expected)
    missing = sorted(expected_current_depth - plan_concepts)
    if missing:
        source_ids = sorted({
            source_id
            for req in research_requirements
            if req.get("concept_key") in missing
            for source_id in req.get("source_ids", [])
        })
        findings.append({
            "dimension": "goal_coverage",
            "severity": "medium" if depth != "ADVANCED" else "high",
            "message": "Plan is missing expected concepts for requested depth.",
            "evidence": {
                "missing_concepts": missing[:8],
                "rubric": rubric.domain,
                "depth": depth,
                "source_ids": source_ids[:8],
            },
        })

    text = normalize_label(" ".join([
        content.get("title") or "",
        content.get("description") or "",
        " ".join(phase.get("title", "") for phase in content.get("phases", [])),
        " ".join(task.get("title", "") for phase in content.get("phases", []) for task in phase.get("tasks", [])),
    ]))
    if rubric.practical_requirements and not any(req in text for req in rubric.practical_requirements):
        findings.append({
            "dimension": "practical_application",
            "severity": "medium",
            "message": "Plan should include practical application or assessment evidence.",
            "evidence": {"expected_terms": rubric.practical_requirements},
        })

    prereq_findings = prerequisite_findings(content, planning_context, rubric)
    findings.extend(prereq_findings)
    return findings


def prerequisite_findings(content: dict, planning_context: dict, rubric: PlanningRubric | None = None) -> list[dict[str, Any]]:
    rubric = rubric or get_rubric(planning_context.get("domain") or content.get("title"))
    plan_keys = _plan_concept_keys(content, rubric.domain)
    prior_keys = {
        item["concept_key"]
        for item in (planning_context.get("coverage_analysis") or {}).get("classifications", [])
        if item.get("decision") in {"ASSUME", "DEEPEN", "SKIP_DUPLICATE"}
    }
    available = plan_keys | prior_keys
    findings = []
    for concept_name, prereqs in rubric.prerequisites.items():
        key = concept_key(concept_name, domain=rubric.domain)
        if key not in plan_keys:
            continue
        missing = [concept_key(p, domain=rubric.domain) for p in prereqs if concept_key(p, domain=rubric.domain) not in available]
        if missing:
            findings.append({
                "dimension": "prerequisite_correctness",
                "severity": "high",
                "message": f"{concept_name} appears without required prerequisites.",
                "evidence": {
                    "concept": key,
                    "missing_prerequisites": missing,
                    "rubric": rubric.domain,
                },
            })
    return findings


def _plan_concept_keys(content: dict, domain: str) -> set[str]:
    keys = set()
    for phase in content.get("phases", []):
        for concept in phase.get("concepts", []):
            keys.add(concept.get("key") or concept_key(concept.get("name"), domain=concept.get("domain") or domain))
        for task in phase.get("tasks", []):
            for concept in task.get("concepts", []):
                keys.add(concept.get("key") or concept_key(concept.get("name"), domain=concept.get("domain") or domain))
    return keys
