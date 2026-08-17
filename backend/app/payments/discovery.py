"""Capability discovery + provider selection.

Discovery answers "which registered providers can satisfy this capability, and are
they usable given this workspace's policy?" Selection then picks ONE of them
deterministically. The LLM may suggest a capability name and constraints, but which
provider actually gets paid is decided by scoring code here — never by model output —
per the "final selection must be validated by backend logic" requirement.
"""
from __future__ import annotations

from typing import Optional

from .models import CapabilityProvider


def discover_providers(capability: str, *, workspace_policy=None) -> list[CapabilityProvider]:
    """List active providers for a capability, filtered by workspace allow/block
    lists. Does not apply cost/latency constraints — that's select_provider's job,
    so callers can still see "what exists" separately from "what's usable now"."""
    query = CapabilityProvider.query.filter_by(capability=capability, is_active=True)
    providers = query.all()

    if workspace_policy is None:
        return providers

    blocked = set(workspace_policy.blocked_providers or [])
    allowed = set(workspace_policy.allowed_providers or [])
    result = [p for p in providers if p.id not in blocked and p.provider not in blocked]
    if allowed:
        result = [p for p in result if p.id in allowed or p.provider in allowed]
    return result


def _score(provider: CapabilityProvider) -> float:
    """Higher is better. Weighted blend of price (lower is better), historical
    success rate, and latency (lower is better) — not "always cheapest"."""
    price = float(provider.price_usdc)
    price_score = 1.0 / (1.0 + price)            # $0 -> 1.0, $1 -> 0.5, $4 -> 0.2
    latency_score = 1.0 / (1.0 + provider.estimated_latency_ms / 2000.0)
    quality_score = provider.success_rate

    return (0.35 * price_score) + (0.30 * quality_score) + (0.20 * latency_score) + (0.15 * provider.success_rate)


def select_provider(
    providers: list[CapabilityProvider],
    *,
    max_cost_usdc: Optional[float] = None,
    max_latency_ms: Optional[int] = None,
) -> Optional[CapabilityProvider]:
    """Deterministic provider selection. Filters by hard constraints first, then
    ranks survivors by _score. Returns None if nothing qualifies (caller must treat
    that as "capability unavailable", not silently skip payment)."""
    candidates = list(providers)
    if max_cost_usdc is not None:
        candidates = [p for p in candidates if float(p.price_usdc) <= max_cost_usdc]
    if max_latency_ms is not None:
        candidates = [p for p in candidates if p.estimated_latency_ms <= max_latency_ms]
    if not candidates:
        return None
    return max(candidates, key=_score)


DEFAULT_PROVIDERS = [
    # Multiple providers per capability, deliberately, so selection has something to
    # choose between rather than always being a single hardcoded option.
    dict(capability="competitor_research", name="MarketScan Pro", provider="marketscan.ai",
         description="Structured competitor landscape report: positioning, pricing, recent moves.",
         endpoint="sim://providers/marketscan/competitor-report",
         price_usdc=0.08, estimated_latency_ms=4500, chain="MATIC-AMOY"),
    dict(capability="competitor_research", name="QuickCompete", provider="quickcompete.io",
         description="Fast, lightweight competitor summary — fewer sources, lower cost.",
         endpoint="sim://providers/quickcompete/summary",
         price_usdc=0.02, estimated_latency_ms=1500, chain="MATIC-AMOY"),
    dict(capability="web_research", name="DeepSearch API", provider="deepsearch.dev",
         description="Multi-source web research with citations for a given topic.",
         endpoint="sim://providers/deepsearch/research",
         price_usdc=0.03, estimated_latency_ms=3000, chain="MATIC-AMOY"),
    dict(capability="data_extraction", name="TableExtract", provider="tableextract.io",
         description="Structured data extraction from documents/pages into JSON.",
         endpoint="sim://providers/tableextract/extract",
         price_usdc=0.05, estimated_latency_ms=2500, chain="MATIC-AMOY"),
    dict(capability="sentiment_analysis", name="SentimentAI", provider="sentimentai.co",
         description="Sentiment + theme analysis over a batch of text/reviews.",
         endpoint="sim://providers/sentimentai/analyze",
         price_usdc=0.04, estimated_latency_ms=2000, chain="MATIC-AMOY"),
]


def seed_default_providers() -> None:
    """Idempotent — inserts the demo provider catalog only if a capability has no
    providers registered yet, mirroring billing.service.seed_plans()'s never-overwrite
    behavior. Lets the Agent Economy be demoable without a manual data-loading step,
    while leaving room for real providers to be registered/removed independently."""
    from ..core.extensions import db

    existing_capabilities = {row[0] for row in db.session.query(CapabilityProvider.capability).distinct()}
    for spec in DEFAULT_PROVIDERS:
        if spec["capability"] in existing_capabilities:
            continue
        db.session.add(CapabilityProvider(**spec))
    db.session.commit()
