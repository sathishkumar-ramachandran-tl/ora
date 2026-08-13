"""Research evidence for rigorous planning.

Research content is treated as untrusted data. It can support planning/rubric
requirements, but it never controls authorization, execution context, or risk policy.
"""
from __future__ import annotations

import hashlib
import ipaddress
import os
import re
import socket
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from ..core.extensions import db
from .coverage import concept_key, infer_domain, normalize_label
from .execution_context import ExecutionContext
from .models import AgentRun, ResearchEvidence


MAX_RESEARCH_SOURCES = 5
MAX_RESEARCH_CLAIMS = 40
MAX_SYNTHESIS_ROUNDS = 1
MAX_RESEARCH_QUERIES = 3
MAX_FETCH_BYTES = 120_000
SAFE_FETCH_SCHEMES = {"http", "https"}


@dataclass(frozen=True)
class ResearchProfile:
    domain: str
    preferred_source_types: list[str]
    canonical_topics: list[str] = field(default_factory=list)
    evidence_requirements: list[str] = field(default_factory=list)
    freshness_days: int | None = None


@dataclass(frozen=True)
class ResearchSearchResult:
    title: str
    url: str | None
    source_type: str
    authority_level: str
    snippet: str = ""


class ResearchProvider(Protocol):
    def search(self, query: str, profile: ResearchProfile) -> list[ResearchSearchResult]:
        ...

    def fetch(self, result: ResearchSearchResult) -> str:
        ...


class ProfileSeedResearchProvider:
    """Bounded provider over curated profile sources.

    It provides deterministic source selection and can fetch the source page live
    when network is available. It is deliberately not a general web crawler.
    """

    def search(self, query: str, profile: ResearchProfile) -> list[ResearchSearchResult]:
        results = []
        query_terms = set(normalize_label(query).split())
        for source in SEED_EVIDENCE.get(profile.domain, []):
            haystack = normalize_label(" ".join([
                source.get("title", ""),
                source.get("topic", ""),
                " ".join(source.get("topics", [])),
            ]))
            if query_terms and not any(term in haystack for term in query_terms if len(term) > 3):
                continue
            results.append(ResearchSearchResult(
                title=source["title"],
                url=source.get("source_url"),
                source_type=source["source_type"],
                authority_level=source["authority_level"],
                snippet=source.get("topic") or "",
            ))
        return results[:MAX_RESEARCH_SOURCES]

    def fetch(self, result: ResearchSearchResult) -> str:
        if os.environ.get("ORA_ENABLE_LIVE_RESEARCH", "false").lower() not in {"1", "true", "yes"}:
            seed = next((
                source for sources in SEED_EVIDENCE.values()
                for source in sources
                if source.get("title") == result.title
            ), None)
            if seed:
                return " ".join(claim.get("claim", "") for claim in seed.get("claims", []))
            return result.snippet
        if not result.url:
            return result.snippet
        _validate_fetch_url(result.url)
        request = Request(result.url, headers={"User-Agent": "OraResearchBot/1.0"})
        # _validate_fetch_url rejects unsafe schemes and private networks.
        with urlopen(request, timeout=8) as response:  # nosec B310
            raw = response.read(MAX_FETCH_BYTES)
        return raw.decode("utf-8", errors="ignore")


def _validate_fetch_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in SAFE_FETCH_SCHEMES or not parsed.hostname:
        raise URLError("Unsupported research URL")

    hostname = parsed.hostname.strip().rstrip(".")
    if hostname.lower() in {"localhost", "metadata.google.internal"}:
        raise URLError("Unsafe research host")

    try:
        addresses = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise URLError("Research host could not be resolved") from exc

    for family, _, _, _, sockaddr in addresses:
        ip = ipaddress.ip_address(sockaddr[0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise URLError("Unsafe research host")


RIGOR_TERMS = (
    "top university", "top-university", "harvard", "stanford", "mit",
    "expert", "advanced", "rigor", "specialization", "current syllabus",
    "latest", "certification", "production grade", "production-grade",
)

SIMPLE_PERSONAL_TERMS = ("groceries", "tomorrow", "weekend errands", "organize tomorrow")

PROMPT_INJECTION_PATTERNS = (
    r"ignore (all )?(previous|prior) instructions",
    r"system prompt",
    r"developer message",
    r"tool authorization",
    r"workspace_id\s*=",
    r"user_id\s*=",
    r"call tool",
    r"execute tool",
)


SEED_EVIDENCE: dict[str, list[dict[str, Any]]] = {
    "computer_networks": [
        {
            "source_type": "official_university_course",
            "title": "MIT 6.829 Computer Networks",
            "source_url": "https://ocw.mit.edu/courses/6-829-computer-networks-fall-2002/",
            "authority_level": "OFFICIAL_UNIVERSITY",
            "topic": "advanced networking",
            "topics": [
                "routing fundamentals", "bgp route policy", "congestion performance",
                "network measurement", "datacenter networking",
            ],
            "claims": [
                {
                    "claim": "Advanced networking requires routing depth before policy analysis.",
                    "topics": ["routing fundamentals", "bgp route policy"],
                    "requirement_type": "prerequisite",
                },
                {
                    "claim": "Advanced plans should include measurement and performance analysis, not only protocol summaries.",
                    "topics": ["network measurement", "congestion performance"],
                    "requirement_type": "advanced_topic",
                },
            ],
        },
        {
            "source_type": "official_university_course",
            "title": "Stanford CS144 Introduction to Computer Networking",
            "source_url": "https://cs144.github.io/",
            "authority_level": "OFFICIAL_UNIVERSITY",
            "topic": "networking fundamentals",
            "topics": ["tcp basics", "tcp congestion control", "routing fundamentals"],
            "claims": [
                {
                    "claim": "TCP behavior and routing foundations are prerequisites for advanced network systems work.",
                    "topics": ["tcp congestion control", "routing fundamentals"],
                    "requirement_type": "prerequisite",
                },
            ],
        },
        {
            "source_type": "official_university_course",
            "title": "CMU Computer Networks",
            "source_url": "https://www.csd.cmu.edu/course/15744/s24",
            "authority_level": "OFFICIAL_UNIVERSITY",
            "topic": "systems networking",
            "topics": ["software defined networking", "datacenter networking", "network security"],
            "claims": [
                {
                    "claim": "Rigorous networking curricula should connect modern architecture topics with labs or projects.",
                    "topics": ["software defined networking", "datacenter networking", "network security"],
                    "requirement_type": "lab_or_project",
                },
            ],
        },
    ],
    "product_mvp": [
        {
            "source_type": "reputable_framework",
            "title": "Startup MVP readiness evidence profile",
            "source_url": None,
            "authority_level": "REPUTABLE",
            "topic": "launch readiness",
            "topics": ["customer validation", "scope discipline", "technical feasibility", "feedback loop"],
            "claims": [
                {
                    "claim": "MVP plans need customer validation, scoped delivery, technical feasibility, launch readiness, and feedback loops.",
                    "topics": ["customer validation", "scope discipline", "technical feasibility", "feedback loop"],
                    "requirement_type": "readiness",
                },
            ],
        },
    ],
}


def get_research_profile(domain: str) -> ResearchProfile:
    if domain == "computer_networks":
        return ResearchProfile(
            domain=domain,
            preferred_source_types=["official_university_course", "canonical_textbook", "primary_technical_source"],
            canonical_topics=[
                "routing fundamentals", "bgp route policy", "congestion performance",
                "network measurement", "datacenter networking", "software defined networking",
            ],
            evidence_requirements=["advanced_topic", "prerequisite", "lab_or_project"],
            freshness_days=None,
        )
    if domain == "exam_preparation":
        return ResearchProfile(
            domain=domain,
            preferred_source_types=["official_exam_authority", "government_source"],
            evidence_requirements=["syllabus", "exam_pattern", "revision"],
            freshness_days=120,
        )
    if domain == "product_mvp":
        return ResearchProfile(
            domain=domain,
            preferred_source_types=["official_docs", "reputable_framework", "primary_research"],
            canonical_topics=["customer validation", "scope discipline", "technical feasibility", "feedback loop"],
            evidence_requirements=["readiness", "risk", "launch"],
            freshness_days=365,
        )
    return ResearchProfile(
        domain=domain,
        preferred_source_types=["official_docs", "primary_source", "reputable_source"],
        evidence_requirements=["coverage", "quality"],
        freshness_days=365,
    )


def plan_research_queries(goal: str, profile: ResearchProfile) -> list[str]:
    text = normalize_label(goal)
    queries = []
    if profile.domain == "computer_networks":
        if "advanced" in text or "specialization" in text:
            queries.extend([
                "advanced computer networking university curriculum",
                "modern networking systems course topics",
                "advanced routing networking syllabus",
            ])
        else:
            queries.append("computer networking university curriculum")
    elif profile.domain == "exam_preparation":
        queries.extend([
            f"official current {goal} syllabus",
            f"official {goal} exam pattern",
        ])
    elif profile.domain == "product_mvp":
        queries.extend([
            "startup MVP launch readiness validation feedback loop",
            "product MVP technical feasibility scope discipline",
        ])
    else:
        queries.append(goal)
    return queries[:MAX_RESEARCH_QUERIES]


def research_needed(goal: str, *, domain: str | None = None) -> bool:
    text = normalize_label(goal)
    if any(term in text for term in SIMPLE_PERSONAL_TERMS):
        return False
    domain = domain or infer_domain(goal)
    if any(term in text for term in RIGOR_TERMS):
        return True
    return domain in {"exam_preparation"} and any(term in text for term in ("syllabus", "exam", "current"))


def interpret_rigor(goal: str) -> dict[str, Any]:
    text = normalize_label(goal)
    if any(term in text for term in ("harvard", "stanford", "mit", "top university", "top-university")):
        return {
            "level": "TOP_UNIVERSITY_RIGOR",
            "requirements": [
                "source_backed_canonical_coverage",
                "prerequisite_correctness",
                "theory_practice_balance",
                "labs_or_projects",
                "assessment_rigor",
                "capstone_integration",
            ],
            "disclaimer": "Rigor target only; no official university equivalence is claimed.",
        }
    if "expert" in text or "advanced" in text:
        return {
            "level": "ADVANCED_RIGOR",
            "requirements": ["conceptual_depth", "practical_application", "assessment_rigor"],
        }
    return {"level": "STANDARD", "requirements": []}


def sanitize_claims(claims: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sanitized: list[dict[str, Any]] = []
    ignored: list[dict[str, Any]] = []
    for claim in claims[:MAX_RESEARCH_CLAIMS]:
        text = str(claim.get("claim") or "")
        if any(re.search(pattern, text, flags=re.I) for pattern in PROMPT_INJECTION_PATTERNS):
            ignored.append({"claim": text, "reason": "prompt_injection_like_instruction"})
            continue
        sanitized.append(claim)
    return sanitized, ignored


def collect_research_evidence(ctx: ExecutionContext, goal: str, *, domain: str | None = None) -> list[ResearchEvidence]:
    domain = domain or infer_domain(goal)
    if not research_needed(goal, domain=domain):
        return []

    profile = get_research_profile(domain)
    cached = _fresh_cached_evidence(ctx.workspace_id, domain, profile)
    if cached:
        return cached[:MAX_RESEARCH_SOURCES]
    run_id = ctx.run_id if ctx.run_id and db.session.get(AgentRun, ctx.run_id) else None

    records: list[ResearchEvidence] = []
    for source in (SEED_EVIDENCE.get(domain) or [])[:MAX_RESEARCH_SOURCES]:
        claims, ignored = sanitize_claims(source.get("claims") or [])
        payload = {
            "title": source["title"],
            "source_url": source.get("source_url"),
            "claims": claims,
            "topics": source.get("topics") or [],
        }
        content_hash = hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()
        existing = ResearchEvidence.query.filter_by(
            workspace_id=ctx.workspace_id,
            domain=domain,
            content_hash=content_hash,
        ).first()
        if existing:
            records.append(existing)
            continue
        record = ResearchEvidence(
            id=str(uuid.uuid4()),
            workspace_id=ctx.workspace_id,
            run_id=run_id,
            domain=domain,
            topic=source.get("topic"),
            source_type=source["source_type"],
            title=source["title"],
            source_url=source.get("source_url"),
            authority_level=source["authority_level"],
            claims=claims,
            topics=[concept_key(topic, domain=domain) for topic in source.get("topics", [])],
            relevance="supports_requested_rigor",
            content_hash=content_hash,
            retrieved_at=datetime.utcnow(),
        )
        if ignored:
            record.relevance = "supports_requested_rigor_with_ignored_instructions"
        db.session.add(record)
        records.append(record)
    db.session.commit()
    return records


def collect_live_research_evidence(
    ctx: ExecutionContext,
    goal: str,
    *,
    domain: str | None = None,
    provider: ResearchProvider | None = None,
) -> dict[str, Any]:
    domain = domain or infer_domain(goal)
    profile = get_research_profile(domain)
    if not research_needed(goal, domain=domain):
        return {"status": "not_required", "evidence": [], "errors": [], "queries": []}

    cached = _fresh_cached_evidence(ctx.workspace_id, domain, profile)
    if cached:
        return {
            "status": "cache_hit",
            "evidence": cached[:MAX_RESEARCH_SOURCES],
            "errors": [],
            "queries": [],
        }

    provider = provider or ProfileSeedResearchProvider()
    queries = plan_research_queries(goal, profile)
    selected: dict[str, ResearchSearchResult] = {}
    errors: list[dict[str, str]] = []
    for query in queries:
        try:
            for result in provider.search(query, profile):
                if _authority_allowed(result, profile):
                    selected[result.url or result.title] = result
                if len(selected) >= MAX_RESEARCH_SOURCES:
                    break
        except Exception as e:
            errors.append({"stage": "search", "query": query, "error": e.__class__.__name__})
        if len(selected) >= MAX_RESEARCH_SOURCES:
            break

    records = []
    for result in list(selected.values())[:MAX_RESEARCH_SOURCES]:
        try:
            content = provider.fetch(result)
        except (URLError, TimeoutError, OSError) as e:
            errors.append({"stage": "fetch", "source": result.title, "error": e.__class__.__name__})
            continue
        claims, ignored = extract_claims_from_source(result, content, domain=domain)
        if not claims:
            continue
        record = _persist_research_source(ctx, domain, result, claims, ignored)
        records.append(record)

    db.session.commit()
    if records:
        status = "succeeded_with_warnings" if errors else "succeeded"
    else:
        fallback = collect_research_evidence(ctx, goal, domain=domain)
        return {
            "status": "fallback_cached_or_seeded" if fallback else "failed",
            "evidence": fallback,
            "errors": errors or [{"stage": "selection", "error": "no_authoritative_sources"}],
            "queries": queries,
        }
    return {"status": status, "evidence": records, "errors": errors, "queries": queries}


def extract_claims_from_source(
    result: ResearchSearchResult,
    content: str,
    *,
    domain: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    text = re.sub(r"<(script|style).*?</\1>", " ", content, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    seed = next((s for s in SEED_EVIDENCE.get(domain, []) if s["title"] == result.title), None)
    claims = list((seed or {}).get("claims") or [])
    topics = (seed or {}).get("topics") or []
    if not claims:
        profile = get_research_profile(domain)
        matched = [topic for topic in profile.canonical_topics if normalize_label(topic) in normalize_label(text)]
        if matched:
            topics = matched
            claims.append({
                "claim": f"Source discusses {', '.join(matched[:6])}.",
                "topics": matched[:8],
                "requirement_type": "coverage",
            })
    sanitized, ignored = sanitize_claims(claims)
    for claim in sanitized:
        claim.setdefault("source_title", result.title)
        claim.setdefault("source_url", result.url)
        claim.setdefault("topics", topics)
    return sanitized, ignored


def synthesize_evidence_requirements(evidence: list[ResearchEvidence]) -> list[dict[str, Any]]:
    requirements: dict[str, dict[str, Any]] = {}
    for source in evidence[:MAX_RESEARCH_SOURCES]:
        for claim in (source.claims or [])[:MAX_RESEARCH_CLAIMS]:
            for topic in claim.get("topics") or []:
                key = concept_key(topic, domain=source.domain)
                req = requirements.setdefault(key, {
                    "concept_key": key,
                    "concept_name": str(topic).title(),
                    "domain": source.domain,
                    "depth": "ADVANCED",
                    "coverage": "INTRODUCES",
                    "source_ids": [],
                    "requirement_types": [],
                    "rationale": [],
                })
                req["source_ids"].append(source.id)
                req["requirement_types"].append(claim.get("requirement_type") or "coverage")
                req["rationale"].append(claim.get("claim"))
    for req in requirements.values():
        req["source_ids"] = sorted(set(req["source_ids"]))
        req["requirement_types"] = sorted(set(req["requirement_types"]))
        req["rationale"] = req["rationale"][:3]
    return sorted(requirements.values(), key=lambda item: item["concept_key"])


def serialize_research_evidence(records: list[ResearchEvidence]) -> list[dict[str, Any]]:
    return [
        {
            "id": record.id,
            "source_type": record.source_type,
            "title": record.title,
            "source_url": record.source_url,
            "authority_level": record.authority_level,
            "domain": record.domain,
            "topic": record.topic,
            "claims": record.claims or [],
            "topics": record.topics or [],
            "relevance": record.relevance,
            "retrieved_at": record.retrieved_at.isoformat() if record.retrieved_at else None,
        }
        for record in records
    ]


def _fresh_cached_evidence(workspace_id: str, domain: str, profile: ResearchProfile) -> list[ResearchEvidence]:
    query = ResearchEvidence.query.filter_by(workspace_id=workspace_id, domain=domain)
    if profile.freshness_days:
        cutoff = datetime.utcnow() - timedelta(days=profile.freshness_days)
        query = query.filter(ResearchEvidence.retrieved_at >= cutoff)
    return query.order_by(ResearchEvidence.retrieved_at.desc()).limit(MAX_RESEARCH_SOURCES).all()


def _authority_allowed(result: ResearchSearchResult, profile: ResearchProfile) -> bool:
    if result.source_type in profile.preferred_source_types:
        return True
    return result.authority_level in {"OFFICIAL_UNIVERSITY", "OFFICIAL_DOCS", "PRIMARY_SOURCE"}


def _persist_research_source(
    ctx: ExecutionContext,
    domain: str,
    result: ResearchSearchResult,
    claims: list[dict[str, Any]],
    ignored: list[dict[str, Any]],
) -> ResearchEvidence:
    payload = {
        "title": result.title,
        "source_url": result.url,
        "claims": claims,
    }
    content_hash = hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()
    existing = ResearchEvidence.query.filter_by(
        workspace_id=ctx.workspace_id,
        domain=domain,
        content_hash=content_hash,
    ).first()
    if existing:
        return existing
    run_id = ctx.run_id if ctx.run_id and db.session.get(AgentRun, ctx.run_id) else None
    topics = sorted({
        concept_key(topic, domain=domain)
        for claim in claims
        for topic in claim.get("topics", [])
    })
    record = ResearchEvidence(
        id=str(uuid.uuid4()),
        workspace_id=ctx.workspace_id,
        run_id=run_id,
        domain=domain,
        topic=result.snippet,
        source_type=result.source_type,
        title=result.title,
        source_url=result.url,
        authority_level=result.authority_level,
        claims=claims,
        topics=topics,
        relevance="live_retrieval_with_ignored_instructions" if ignored else "live_retrieval",
        content_hash=content_hash,
        retrieved_at=datetime.utcnow(),
    )
    db.session.add(record)
    return record
