"""Agentic capability purchase — shared logic behind the acquire_capability tool.

Same shape as task_tools.py/calendar_tools.py: a thin wrapper returning
{"success", "data", "error"}, callable from both the LangChain tool in
app/agents/tools.py and (in principle) an MCP client. The actual purchase pipeline
(discovery -> policy -> Circle payment -> provider call -> verification -> evidence)
lives in app/payments/service.py; this module only adapts its result shape and keeps
the agent-facing surface intentionally narrow.
"""
from typing import Optional


def acquire_capability(capability: str, task: str, reason: str = "",
                        max_cost_usdc: Optional[float] = None,
                        max_latency_ms: Optional[int] = None) -> dict:
    from ..payments.service import acquire_capability as _acquire

    constraints = {}
    if max_cost_usdc is not None:
        constraints["max_cost_usdc"] = max_cost_usdc
    if max_latency_ms is not None:
        constraints["max_latency_ms"] = max_latency_ms

    return _acquire(capability=capability, task=task, reason=reason, constraints=constraints)
