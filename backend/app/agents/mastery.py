"""Evidence-backed mastery/competency helpers.

Coverage says a plan exposed a concept. Mastery changes only when explicit evidence
is recorded here.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from ..core.extensions import db
from .coverage import concept_key, upsert_concept
from .execution_context import ExecutionContext
from .models import CompetencyEvidence, MasteryRecord


MASTERY_STATUSES = {"UNKNOWN", "INTRODUCED", "PRACTICED", "PROFICIENT", "STRONG", "NEEDS_REVIEW"}


def record_competency_evidence(
    ctx: ExecutionContext,
    *,
    concept_name: str,
    domain: str,
    evidence_type: str,
    result: dict[str, Any],
    strength: str | None = None,
    evidence_ref: str | None = None,
) -> tuple[CompetencyEvidence, MasteryRecord]:
    concept = upsert_concept(ctx.workspace_id, concept_name, domain=domain, key=concept_key(concept_name, domain=domain))
    status, resolved_strength = mastery_status_from_evidence(evidence_type, result, strength=strength)
    evidence = CompetencyEvidence(
        id=str(uuid.uuid4()),
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        concept_id=concept.id,
        evidence_type=evidence_type,
        evidence_ref=evidence_ref,
        result=result,
        strength=resolved_strength,
        assessed_at=datetime.utcnow(),
    )
    db.session.add(evidence)
    db.session.flush()

    mastery = MasteryRecord.query.filter_by(
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        concept_id=concept.id,
    ).first()
    if not mastery:
        mastery = MasteryRecord(
            id=str(uuid.uuid4()),
            workspace_id=ctx.workspace_id,
            user_id=ctx.user_id,
            concept_id=concept.id,
            concept_key=concept.concept_key,
        )
        db.session.add(mastery)

    mastery.status = status
    mastery.evidence_type = evidence.evidence_type
    mastery.evidence_id = evidence.id
    mastery.assessed_at = evidence.assessed_at
    db.session.commit()
    return evidence, mastery


def mastery_status_from_evidence(evidence_type: str, result: dict[str, Any], *, strength: str | None = None) -> tuple[str, str]:
    normalized_strength = (strength or result.get("strength") or "WEAK").upper()
    if normalized_strength not in {"WEAK", "MODERATE", "STRONG"}:
        normalized_strength = "WEAK"
    if result.get("status") == "needs_review" or result.get("passed") is False:
        return "NEEDS_REVIEW", normalized_strength

    if evidence_type == "assessment":
        score = result.get("score")
        if isinstance(score, (int, float)):
            if score >= 0.85:
                return "STRONG", "STRONG"
            if score >= 0.7:
                return "PROFICIENT", "MODERATE"
            return "NEEDS_REVIEW", "MODERATE"
        return ("PROFICIENT", "MODERATE") if result.get("passed") else ("NEEDS_REVIEW", "MODERATE")

    if evidence_type == "project_artifact":
        if normalized_strength == "STRONG" or result.get("passed"):
            return "STRONG", "STRONG"
        return "PROFICIENT", normalized_strength

    if evidence_type == "manual_confirmation":
        return ("STRONG", "STRONG") if normalized_strength == "STRONG" else ("PROFICIENT", normalized_strength)

    if evidence_type == "self_report":
        if normalized_strength == "STRONG":
            return "PRACTICED", normalized_strength
        return "INTRODUCED", normalized_strength

    return "UNKNOWN", normalized_strength


def mastery_for_workspace(ctx: ExecutionContext, *, domain: str | None = None) -> list[MasteryRecord]:
    query = MasteryRecord.query.filter_by(workspace_id=ctx.workspace_id, user_id=ctx.user_id)
    if domain:
        query = query.filter(MasteryRecord.concept_key.like(f"{domain}.%"))
    return query.order_by(MasteryRecord.updated_at.desc()).all()


def serialize_mastery(records: list[MasteryRecord]) -> list[dict[str, Any]]:
    return [
        {
            "id": record.id,
            "concept_key": record.concept_key,
            "status": record.status,
            "evidence_type": record.evidence_type,
            "evidence_id": record.evidence_id,
            "assessed_at": record.assessed_at.isoformat() if record.assessed_at else None,
        }
        for record in records
    ]
