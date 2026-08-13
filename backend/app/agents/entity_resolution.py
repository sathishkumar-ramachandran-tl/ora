"""Deterministic entity resolution helpers for scoped agent actions."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from ..core.extensions import db
from .execution_context import ExecutionContext


class ResolutionState(str, Enum):
    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_FOUND = "NOT_FOUND"


@dataclass
class ResolutionResult:
    state: ResolutionState
    entity_type: str
    entity: Optional[Any] = None
    matches: Optional[list[Any]] = None
    message: str = ""


def resolve_task(ctx: ExecutionContext, reference: str | None = None, explicit_id: str | None = None) -> ResolutionResult:
    from .. import models as m

    if explicit_id:
        task = db.session.get(m.Task, explicit_id)
        if task and task.workspace_id == ctx.workspace_id:
            return ResolutionResult(ResolutionState.RESOLVED, "task", task)
        return ResolutionResult(ResolutionState.NOT_FOUND, "task", message="Task not found")

    if ctx.scope_task_id:
        task = db.session.get(m.Task, ctx.scope_task_id)
        if task and task.workspace_id == ctx.workspace_id:
            return ResolutionResult(ResolutionState.RESOLVED, "task", task)

    query = m.Task.query.filter_by(workspace_id=ctx.workspace_id)
    if ctx.scope_project_id:
        query = query.filter_by(project_id=ctx.scope_project_id)

    if reference:
        matches = query.filter(m.Task.title.ilike(reference.strip())).all()
        if not matches:
            matches = query.filter(m.Task.title.ilike(f"%{reference.strip()}%")).all()
        return _resolution("task", matches)

    return ResolutionResult(ResolutionState.NOT_FOUND, "task", message="No task reference supplied")


def resolve_project(ctx: ExecutionContext, reference: str | None = None, explicit_id: str | None = None) -> ResolutionResult:
    from .. import models as m

    if explicit_id:
        project = db.session.get(m.Project, explicit_id)
        if project and project.workspace_id == ctx.workspace_id:
            return ResolutionResult(ResolutionState.RESOLVED, "project", project)
        return ResolutionResult(ResolutionState.NOT_FOUND, "project", message="Project not found")

    if ctx.scope_project_id:
        project = db.session.get(m.Project, ctx.scope_project_id)
        if project and project.workspace_id == ctx.workspace_id:
            return ResolutionResult(ResolutionState.RESOLVED, "project", project)

    query = m.Project.query.filter_by(workspace_id=ctx.workspace_id)
    if reference:
        matches = query.filter(m.Project.name.ilike(reference.strip())).all()
        if not matches:
            matches = query.filter(m.Project.name.ilike(f"%{reference.strip()}%")).all()
        return _resolution("project", matches)

    return ResolutionResult(ResolutionState.NOT_FOUND, "project", message="No project reference supplied")


def _resolution(entity_type: str, matches: list[Any]) -> ResolutionResult:
    if len(matches) == 1:
        return ResolutionResult(ResolutionState.RESOLVED, entity_type, matches[0], matches)
    if len(matches) > 1:
        return ResolutionResult(ResolutionState.AMBIGUOUS, entity_type, None, matches, "Multiple matches found")
    return ResolutionResult(ResolutionState.NOT_FOUND, entity_type, None, [], "No matches found")

