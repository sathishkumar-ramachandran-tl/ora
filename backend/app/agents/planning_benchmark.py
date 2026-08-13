"""Repeatable planning benchmark harness.

The harness evaluates structured plan outputs and coverage continuity. It does not grade
pretty prose.
"""
from __future__ import annotations

from .execution_context import ExecutionContext, execution_context
from .planning import apply_plan_proposal, create_plan_proposal, serialize_plan


COMPUTER_NETWORKS_SCENARIOS = [
    ("A", "Create a beginner Computer Networks curriculum."),
    ("B", "Create Intermediate Computer Networks."),
    ("C", "Create an advanced top-university-level Computer Networks specialization."),
]


def run_computer_networks_benchmark(ctx: ExecutionContext) -> list[dict]:
    results = []
    with execution_context(ctx):
        for label, goal in COMPUTER_NETWORKS_SCENARIOS:
            proposal = create_plan_proposal(ctx, goal)
            serialized = serialize_plan(proposal)
            differential = (serialized["content"] or {}).get("differential") or {}
            results.append({
                "scenario": label,
                "goal": goal,
                "prior_context_retrieved": len((serialized.get("planningContext") or {}).get("coverage_records") or []),
                "coverage_classifications": (serialized.get("planningContext") or {}).get("coverage_analysis", {}).get("classifications", []),
                "quality_findings": (serialized.get("qualityReport") or {}).get("findings", []),
                "revision_count": 0,
                "final_proposal_summary": serialized["summary"],
                "duplicates_avoided": len(differential.get("skipped_as_duplicate") or []),
                "new_concepts_added": len(differential.get("adds") or []),
            })
            apply_plan_proposal(proposal.id)
    return results
