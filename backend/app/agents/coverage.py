"""Persistent concept and coverage continuity helpers."""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Iterable, Optional

from ..core.extensions import db
from .models import Concept, ConceptAlias, ConceptRelationship, CoverageRecord, PlanProposal


COVERAGE_TYPES = {"INTRODUCES", "PRACTICES", "DEEPENS", "ASSESSES", "REVIEWS"}
DEPTHS = {"FOUNDATIONAL", "INTERMEDIATE", "ADVANCED"}
RELATIONSHIPS = {"REQUIRES", "BUILDS_ON", "RELATED_TO"}


def normalize_label(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def concept_key(value: str | None, *, domain: str | None = None) -> str:
    normalized = normalize_label(value).replace(" ", "_")
    if not normalized:
        normalized = "unknown"
    domain_prefix = normalize_label(domain).replace(" ", "_")
    return f"{domain_prefix}.{normalized}" if domain_prefix else normalized


def infer_domain(goal_or_title: str | None) -> str:
    text = normalize_label(goal_or_title)
    if any(term in text for term in ("network", "tcp", "routing", "bgp", "dns", "subnet")):
        return "computer_networks"
    if any(term in text for term in ("exam", "upsc", "syllabus", "mock test")):
        return "exam_preparation"
    if any(term in text for term in ("mvp", "startup", "launch", "product")):
        return "product_mvp"
    if any(term in text for term in ("machine learning", "ml", "model training")):
        return "machine_learning"
    return "general"


def infer_requested_depth(goal: str | None) -> str:
    text = normalize_label(goal)
    if any(term in text for term in ("advanced", "expert", "top university", "rigor", "specialization")):
        return "ADVANCED"
    if any(term in text for term in ("intermediate", "deepen", "next level")):
        return "INTERMEDIATE"
    return "FOUNDATIONAL"


def upsert_concept(workspace_id: str, name: str, *, domain: str | None = None, key: str | None = None) -> Concept:
    key = key or concept_key(name, domain=domain)
    concept = Concept.query.filter_by(workspace_id=workspace_id, concept_key=key).first()
    if concept:
        return concept
    concept = Concept(workspace_id=workspace_id, concept_key=key, canonical_name=name, domain=domain)
    db.session.add(concept)
    db.session.flush()
    alias_norm = normalize_label(name)
    if alias_norm:
        db.session.add(ConceptAlias(concept_id=concept.id, alias=name, normalized_alias=alias_norm))
    return concept


def add_concept_relationship(
    workspace_id: str,
    source: Concept,
    target: Concept,
    relationship_type: str,
    *,
    evidence: Optional[dict] = None,
) -> ConceptRelationship:
    relationship_type = relationship_type if relationship_type in RELATIONSHIPS else "RELATED_TO"
    existing = ConceptRelationship.query.filter_by(
        source_concept_id=source.id,
        target_concept_id=target.id,
        relationship_type=relationship_type,
    ).first()
    if existing:
        return existing
    rel = ConceptRelationship(
        workspace_id=workspace_id,
        source_concept_id=source.id,
        target_concept_id=target.id,
        relationship_type=relationship_type,
        evidence=evidence or {},
    )
    db.session.add(rel)
    return rel


def iter_plan_semantics(content: dict) -> Iterable[dict[str, Any]]:
    for phase in content.get("phases", []):
        for concept in phase.get("concepts", []):
            yield {
                **concept,
                "source_type": "milestone",
                "source_id": phase.get("id"),
                "source_title": phase.get("title"),
            }
        for task in phase.get("tasks", []):
            for concept in task.get("concepts", []):
                yield {
                    **concept,
                    "source_type": "task",
                    "source_id": task.get("id"),
                    "source_title": task.get("title"),
                }


def create_coverage_records_for_plan(proposal: PlanProposal, project_id: str | None = None) -> list[CoverageRecord]:
    records = []
    domain = infer_domain(f"{proposal.title} {proposal.goal}")
    for semantic in iter_plan_semantics(proposal.content or {}):
        name = semantic.get("name") or semantic.get("concept_name") or semantic.get("key") or semantic.get("concept_key")
        key = semantic.get("key") or semantic.get("concept_key") or concept_key(name, domain=semantic.get("domain") or domain)
        coverage_type = semantic.get("coverage") or semantic.get("coverage_type") or "INTRODUCES"
        depth = semantic.get("depth") or infer_requested_depth(proposal.goal)
        if coverage_type not in COVERAGE_TYPES:
            coverage_type = "INTRODUCES"
        if depth not in DEPTHS:
            depth = infer_requested_depth(proposal.goal)

        concept = upsert_concept(proposal.workspace_id, name or key, domain=semantic.get("domain") or domain, key=key)
        existing = CoverageRecord.query.filter_by(
            workspace_id=proposal.workspace_id,
            plan_proposal_id=proposal.id,
            concept_key=concept.concept_key,
            coverage_type=coverage_type,
            depth=depth,
            source_type=semantic.get("source_type") or "plan",
            source_id=semantic.get("source_id"),
        ).first()
        if existing:
            records.append(existing)
            continue
        record = CoverageRecord(
            workspace_id=proposal.workspace_id,
            project_id=project_id or proposal.scope_project_id,
            plan_proposal_id=proposal.id,
            concept_id=concept.id,
            concept_key=concept.concept_key,
            concept_name=concept.canonical_name,
            domain=concept.domain,
            coverage_type=coverage_type,
            depth=depth,
            status="PLANNED",
            source_type=semantic.get("source_type") or "plan",
            source_id=semantic.get("source_id"),
            evidence={
                "source_title": semantic.get("source_title"),
                "provenance": "plan_semantic_annotation",
                "source_ids": semantic.get("source_ids", []),
                "rationale": semantic.get("rationale", []),
            },
        )
        db.session.add(record)
        records.append(record)

        for prereq in semantic.get("prerequisites", []) or []:
            prereq_key = prereq.get("key") if isinstance(prereq, dict) else prereq
            prereq_name = prereq.get("name") if isinstance(prereq, dict) else str(prereq).replace("_", " ")
            prereq_concept = upsert_concept(proposal.workspace_id, prereq_name, domain=concept.domain, key=prereq_key)
            add_concept_relationship(
                proposal.workspace_id,
                concept,
                prereq_concept,
                "REQUIRES",
                evidence={"source": "plan_semantic_annotation", "plan_proposal_id": proposal.id},
            )
    db.session.commit()
    return records


def coverage_for_workspace(
    workspace_id: str,
    *,
    domain: str | None = None,
    project_ids: Optional[list[str]] = None,
) -> list[CoverageRecord]:
    query = CoverageRecord.query.filter_by(workspace_id=workspace_id)
    if domain:
        query = query.filter_by(domain=domain)
    if project_ids:
        query = query.filter(CoverageRecord.project_id.in_(project_ids))
    return query.order_by(CoverageRecord.created_at.asc()).all()


def lazy_extract_coverage_from_tasks(workspace_id: str, tasks: list[dict], *, domain: str | None = None) -> list[CoverageRecord]:
    """Backfill lightweight coverage from pre-feature tasks when a project is reused.

    This records exposure/work coverage only. It does not infer mastery.
    """
    records = []
    domain = domain or "general"
    for task in tasks:
        title = task.get("title")
        if not title:
            continue
        key = concept_key(title, domain=domain)
        existing = CoverageRecord.query.filter_by(
            workspace_id=workspace_id,
            concept_key=key,
            source_type="task",
            source_id=task.get("id"),
        ).first()
        if existing:
            records.append(existing)
            continue
        concept = upsert_concept(workspace_id, title, domain=domain, key=key)
        status = "COMPLETED" if task.get("status") == "done" else "IN_PROGRESS" if task.get("status") == "in-progress" else "PLANNED"
        record = CoverageRecord(
            workspace_id=workspace_id,
            project_id=task.get("project_id"),
            concept_id=concept.id,
            concept_key=concept.concept_key,
            concept_name=concept.canonical_name,
            domain=concept.domain,
            coverage_type="INTRODUCES",
            depth="FOUNDATIONAL",
            status=status,
            source_type="task",
            source_id=task.get("id"),
            evidence={"provenance": "lazy_task_title_extraction"},
        )
        db.session.add(record)
        records.append(record)
    db.session.commit()
    return records


def summarize_coverage(records: list[CoverageRecord]) -> dict:
    by_depth: dict[str, set[str]] = defaultdict(set)
    by_status: dict[str, set[str]] = defaultdict(set)
    review = set()
    for record in records:
        by_depth[record.depth].add(record.concept_key)
        by_status[record.status].add(record.concept_key)
        if record.status == "NEEDS_REVIEW" or record.coverage_type == "REVIEWS":
            review.add(record.concept_name)
    return {
        "total_concepts": len({r.concept_key for r in records}),
        "by_depth": {k: len(v) for k, v in by_depth.items()},
        "by_status": {k: len(v) for k, v in by_status.items()},
        "review_concepts": sorted(review)[:12],
    }


def classify_prior_coverage(goal: str, records: list[CoverageRecord], mastery_records: list[Any] | None = None) -> dict:
    requested_depth = infer_requested_depth(goal)
    classifications = []
    seen: dict[str, CoverageRecord] = {}
    mastery_by_key = {record.concept_key: record for record in mastery_records or []}
    depth_rank = {"FOUNDATIONAL": 1, "INTERMEDIATE": 2, "ADVANCED": 3}
    requested_rank = depth_rank[requested_depth]
    for record in records:
        current = seen.get(record.concept_key)
        if not current or depth_rank.get(record.depth, 0) >= depth_rank.get(current.depth, 0):
            seen[record.concept_key] = record

    for record in seen.values():
        rank = depth_rank.get(record.depth, 0)
        mastery = mastery_by_key.get(record.concept_key)
        mastery_status = mastery.status if mastery else None
        if mastery_status == "NEEDS_REVIEW" or record.status == "NEEDS_REVIEW":
            decision = "REVIEW"
        elif mastery_status in {"STRONG", "PROFICIENT"} and rank >= requested_rank - 1:
            decision = "ASSUME" if rank < requested_rank else "SKIP_DUPLICATE"
        elif rank >= requested_rank:
            decision = "SKIP_DUPLICATE"
        elif requested_rank - rank == 1:
            decision = "DEEPEN"
        else:
            decision = "ASSUME"
        classifications.append({
            "concept_key": record.concept_key,
            "concept_name": record.concept_name,
            "prior_depth": record.depth,
            "prior_status": record.status,
            "mastery_status": mastery_status,
            "decision": decision,
            "evidence": {
                "coverage_record_id": record.id,
                "plan_proposal_id": record.plan_proposal_id,
                "mastery_record_id": mastery.id if mastery else None,
            },
        })
    return {
        "requested_depth": requested_depth,
        "classifications": sorted(classifications, key=lambda item: item["concept_key"]),
    }
