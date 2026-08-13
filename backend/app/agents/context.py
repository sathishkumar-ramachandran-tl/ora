"""Structured context assembly for agent prompts.

This replaces ad-hoc prompt dictionaries with a small, explicit envelope. It is not a
retrieval system yet; it simply makes scope and trusted identity deterministic.
"""
from __future__ import annotations

from typing import Iterable

from ..core.extensions import db
from .execution_context import ExecutionContext


def build_context_envelope(ctx: ExecutionContext, recent_messages: Iterable | None = None) -> dict:
    from .. import models as m

    workspace = db.session.get(m.Workspace, ctx.workspace_id)
    user = db.session.get(m.User, ctx.user_id)
    envelope = {
        "user": {
            "id": ctx.user_id,
            "timezone": "UTC",
        },
        "workspace": {
            "id": ctx.workspace_id,
            "name": workspace.name if workspace else None,
            "persona": workspace.persona if workspace else None,
        },
        "scope": {
            "level": ctx.scope_level or "workspace",
            "workspace_id": ctx.workspace_id,
            "project_id": ctx.scope_project_id,
            "task_id": ctx.scope_task_id,
        },
        "scoped_entity": None,
        "relevant_entities": {
            "projects": [],
            "tasks": [],
        },
        "recent_conversation": [],
    }
    if user and getattr(user, "timezone", None):
        envelope["user"]["timezone"] = user.timezone

    project_ids: list[str] = []
    if ctx.scope_project_id:
        project = db.session.get(m.Project, ctx.scope_project_id)
        if project and project.workspace_id == ctx.workspace_id:
            envelope["scoped_entity"] = {
                "type": "project",
                "id": project.id,
                "name": project.name,
                "mission": project.mission,
            }
            project_ids.append(project.id)
    elif ctx.scope_task_id:
        task = db.session.get(m.Task, ctx.scope_task_id)
        if task and task.workspace_id == ctx.workspace_id:
            envelope["scoped_entity"] = {
                "type": "task",
                "id": task.id,
                "title": task.title,
                "status": task.status,
                "project_id": task.project_id,
            }
            project_ids.append(task.project_id)
    else:
        projects = m.Project.query.filter_by(workspace_id=ctx.workspace_id).limit(20).all()
        project_ids = [p.id for p in projects]
        envelope["relevant_entities"]["projects"] = [
            {"id": p.id, "name": p.name, "type": p.type, "progress": p.progress}
            for p in projects
        ]

    if project_ids:
        tasks = m.Task.query.filter(m.Task.project_id.in_(project_ids)).limit(50).all()
    else:
        tasks = m.Task.query.filter_by(workspace_id=ctx.workspace_id).limit(50).all()
    envelope["relevant_entities"]["tasks"] = [
        {
            "id": t.id,
            "title": t.title,
            "status": t.status,
            "priority": t.priority,
            "project_id": t.project_id,
            "milestone_id": t.milestone_id,
            "sprint_id": t.sprint_id,
        }
        for t in tasks
    ]

    for msg in list(recent_messages or [])[-8:]:
        envelope["recent_conversation"].append({
            "role": getattr(msg, "role", None),
            "content": (getattr(msg, "content", "") or "")[:500],
        })

    return envelope

