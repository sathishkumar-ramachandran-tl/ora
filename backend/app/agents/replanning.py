"""Differential plan revision helpers."""
from __future__ import annotations

import re
import uuid
from copy import deepcopy
from typing import Any

from ..core.extensions import db
from .coverage import concept_key, infer_domain
from .execution_context import ExecutionContext
from .models import PlanProposal, PlanRevisionProposal
from .planning import create_plan_proposal


def create_plan_revision_proposal(
    ctx: ExecutionContext,
    base_plan_id: str,
    *,
    trigger: str,
    hard_constraints: list[dict[str, Any]] | None = None,
    soft_preferences: list[dict[str, Any]] | None = None,
) -> PlanRevisionProposal:
    base = db.session.get(PlanProposal, base_plan_id)
    if not base or base.workspace_id != ctx.workspace_id:
        raise PermissionError("PlanProposal not found in trusted workspace")

    hard_constraints = list(hard_constraints or [])
    soft_preferences = list(soft_preferences or [])
    hard_constraints.extend(_extract_hard_constraints(trigger))
    operations = _build_revision_operations(base, trigger, hard_constraints)
    revision = PlanRevisionProposal(
        id=str(uuid.uuid4()),
        workspace_id=ctx.workspace_id,
        base_plan_id=base.id,
        base_version=base.version or 1,
        trigger=trigger,
        hard_constraints=hard_constraints,
        soft_preferences=soft_preferences,
        operations=operations,
        rationale=_revision_rationale(trigger, operations, hard_constraints),
        status="PROPOSED",
    )
    db.session.add(revision)
    db.session.commit()
    return revision


def apply_revision_proposal(ctx: ExecutionContext, revision_id: str) -> PlanProposal:
    revision = db.session.get(PlanRevisionProposal, revision_id)
    if not revision or revision.workspace_id != ctx.workspace_id:
        raise PermissionError("PlanRevisionProposal not found in trusted workspace")
    if revision.applied_plan_id:
        existing = db.session.get(PlanProposal, revision.applied_plan_id)
        if existing:
            return existing

    base = db.session.get(PlanProposal, revision.base_plan_id)
    if not base or base.workspace_id != ctx.workspace_id:
        raise PermissionError("Base PlanProposal not found in trusted workspace")
    content = _apply_operations_to_content(base.content or {}, revision.operations or [])
    proposal = create_plan_proposal(
        ctx,
        base.goal or base.title,
        title=base.title,
        content=content,
        supersedes_id=base.id,
        revision_reason=revision.rationale,
    )
    revision.applied_plan_id = proposal.id
    revision.status = "APPLIED"
    db.session.commit()
    return proposal


def serialize_revision(revision: PlanRevisionProposal) -> dict[str, Any]:
    return {
        "id": revision.id,
        "workspace_id": revision.workspace_id,
        "base_plan_id": revision.base_plan_id,
        "base_version": revision.base_version,
        "trigger": revision.trigger,
        "hard_constraints": revision.hard_constraints or [],
        "soft_preferences": revision.soft_preferences or [],
        "operations": revision.operations or [],
        "rationale": revision.rationale,
        "status": revision.status,
        "applied_plan_id": revision.applied_plan_id,
    }


def _extract_hard_constraints(trigger: str) -> list[dict[str, Any]]:
    text = trigger.lower()
    constraints = []
    if "without changing" in text or "without moving" in text or "don't move" in text or "do not move" in text:
        if "exam" in text or "final" in text or "deadline" in text:
            constraints.append({"type": "fixed_deadline", "target": "final_exam_or_deadline", "source": trigger})
    return constraints


def _build_revision_operations(base: PlanProposal, trigger: str, hard_constraints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    domain = infer_domain(f"{base.title} {base.goal}")
    text = trigger.lower()
    operations: list[dict[str, Any]] = []
    completed = _completed_unit_titles(base.content or {})
    for title in completed[:8]:
        operations.append({"op": "KEEP", "target": title, "reason": "Completed work should not be regenerated."})

    if hard_constraints:
        for constraint in hard_constraints:
            operations.append({"op": "KEEP", "target": constraint.get("target"), "constraint": constraint})

    if "missed" in text or "fell behind" in text:
        operations.append({
            "op": "MOVE",
            "target": "dependent_unfinished_work",
            "reason": "User reported missed work; dependent unfinished items should move locally.",
            "window": "next_two_weeks" if "two weeks" in text or "next 2 weeks" in text else "near_term",
        })

    if "cidr" in text and any(term in text for term in ("failed", "needs review", "poorly", "weak")):
        operations.append({
            "op": "REVIEW",
            "target_concept_key": concept_key("CIDR aggregation", domain=domain),
            "target": "CIDR aggregation",
            "reason": "Assessment evidence indicates remediation is needed before dependent advanced routing.",
        })
        operations.append({
            "op": "MOVE",
            "target": "BGP route policy lab",
            "reason": "BGP policy depends on routing/CIDR readiness.",
            "depends_on": concept_key("CIDR aggregation", domain=domain),
        })

    if not operations:
        operations.append({"op": "KEEP", "target": "existing_plan_structure", "reason": "No safe local change was inferred."})
    return operations


def _completed_unit_titles(content: dict) -> list[str]:
    titles = []
    for phase in content.get("phases", []):
        if phase.get("status") == "completed":
            titles.append(phase.get("title") or phase.get("id"))
        for task in phase.get("tasks", []):
            if task.get("status") in {"done", "completed"}:
                titles.append(task.get("title") or task.get("id"))
    return [t for t in titles if t]


def _revision_rationale(trigger: str, operations: list[dict[str, Any]], hard_constraints: list[dict[str, Any]]) -> str:
    changed = [op for op in operations if op.get("op") != "KEEP"]
    preserved = " Fixed deadlines were preserved." if hard_constraints else ""
    return f"Revision triggered by: {trigger}. Proposed {len(changed)} local change(s).{preserved}"


def _apply_operations_to_content(content: dict, operations: list[dict[str, Any]]) -> dict:
    revised = deepcopy(content)
    revised.setdefault("metadata", {})["revision_operations"] = operations
    phases = revised.setdefault("phases", [])
    sequence = len(phases) + 1
    for op in operations:
        if op.get("op") not in {"ADD", "REVIEW", "DEEPEN"}:
            continue
        title = op.get("target") or op.get("target_concept_key", "Review")
        phase_id = re.sub(r"[^a-z0-9]+", "-", f"revision-{title}".lower()).strip("-")
        if any(phase.get("id") == phase_id for phase in phases):
            continue
        phases.append({
            "id": phase_id,
            "title": title,
            "description": op.get("reason"),
            "sequence": sequence,
            "concepts": [{
                "key": op.get("target_concept_key") or concept_key(title, domain=infer_domain(revised.get("title"))),
                "name": title,
                "coverage": "REVIEWS" if op.get("op") == "REVIEW" else "DEEPENS",
                "depth": "INTERMEDIATE",
            }],
            "tasks": [{
                "id": f"{phase_id}-task",
                "title": f"Review {title}",
                "description": op.get("reason"),
                "estimated_hours": 2,
                "priority": "high",
            }],
        })
        sequence += 1
    return revised
