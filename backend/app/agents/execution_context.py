"""Trusted execution context for agent and MCP initiated work.

This context is created by authenticated application entrypoints. Tool arguments from
LLMs must not be allowed to override these values.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator, Optional


@dataclass(frozen=True)
class ExecutionContext:
    request_id: str
    user_id: str
    workspace_id: str
    session_id: Optional[str] = None
    run_id: Optional[str] = None
    scope_level: str = "workspace"
    scope_project_id: Optional[str] = None
    scope_task_id: Optional[str] = None


_current_context: ContextVar[ExecutionContext | None] = ContextVar("ora_execution_context", default=None)


@contextmanager
def execution_context(ctx: ExecutionContext) -> Iterator[ExecutionContext]:
    token = _current_context.set(ctx)
    try:
        yield ctx
    finally:
        _current_context.reset(token)


def get_execution_context(required: bool = True) -> ExecutionContext | None:
    ctx = _current_context.get()
    if required and ctx is None:
        raise RuntimeError("ExecutionContext is required for this operation")
    return ctx

