"""PlanProposal API endpoints."""
from __future__ import annotations

import uuid

from flask import Blueprint, jsonify, request, g
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..core.extensions import db
from ..workspaces.models import WorkspaceMember
from .action_executor import create_agent_run
from .execution_context import ExecutionContext, execution_context
from .models import PlanProposal
from .planning import (
    apply_plan_proposal,
    create_plan_proposal,
    request_plan_confirmation,
    serialize_plan,
)

plan_bp = Blueprint("plans", __name__)


def _ctx(workspace_id: str, session_id: str | None = None, run_id: str | None = None, scope: dict | None = None) -> ExecutionContext:
    scope = scope or {}
    return ExecutionContext(
        request_id=getattr(g, "request_id", None) or str(uuid.uuid4()),
        user_id=get_jwt_identity(),
        workspace_id=workspace_id,
        session_id=session_id,
        run_id=run_id or str(uuid.uuid4()),
        scope_level=scope.get("scope_level") or "workspace",
        scope_project_id=scope.get("scope_project_id"),
        scope_task_id=scope.get("scope_task_id"),
    )


def _workspace_access(user_id: str, workspace_id: str) -> bool:
    from ..core.authz import user_can_access_workspace
    return bool(user_can_access_workspace(user_id, workspace_id) or WorkspaceMember.query.filter_by(
        workspace_id=workspace_id, user_id=user_id
    ).first())


@plan_bp.route("/plans", methods=["POST"])
@jwt_required()
def create_plan():
    user_id = get_jwt_identity()
    data = request.json or {}
    workspace_id = data.get("workspace_id") or data.get("workspaceId")
    goal = (data.get("goal") or "").strip()
    if not workspace_id or not goal:
        return jsonify({"error": "workspace_id and goal required"}), 400
    if not _workspace_access(user_id, workspace_id):
        return jsonify({"error": "Access denied"}), 403

    scope = {
        "scope_level": data.get("scope_level") or data.get("scopeLevel") or "workspace",
        "scope_project_id": data.get("scope_project_id") or data.get("scopeProjectId"),
        "scope_task_id": data.get("scope_task_id") or data.get("scopeTaskId"),
    }
    ctx = _ctx(workspace_id, data.get("session_id") or data.get("sessionId"), scope=scope)
    create_agent_run(ctx)
    with execution_context(ctx):
        proposal = create_plan_proposal(
            ctx,
            goal,
            title=data.get("title"),
            content=data.get("content"),
            supersedes_id=data.get("supersedes_id") or data.get("supersedesId"),
            revision_reason=data.get("revision_reason") or data.get("revisionReason"),
        )
    return jsonify(serialize_plan(proposal)), 201


@plan_bp.route("/plans/<proposal_id>", methods=["GET"])
@jwt_required()
def get_plan(proposal_id):
    user_id = get_jwt_identity()
    proposal = db.session.get(PlanProposal, proposal_id)
    if not proposal or not _workspace_access(user_id, proposal.workspace_id):
        return jsonify({"error": "PlanProposal not found"}), 404
    return jsonify(serialize_plan(proposal))


@plan_bp.route("/plans/<proposal_id>/confirm", methods=["POST"])
@jwt_required()
def confirm_plan(proposal_id):
    proposal = db.session.get(PlanProposal, proposal_id)
    if not proposal:
        return jsonify({"error": "PlanProposal not found"}), 404
    ctx = _ctx(proposal.workspace_id, run_id=str(uuid.uuid4()), scope={
        "scope_level": proposal.scope_level,
        "scope_project_id": proposal.scope_project_id,
        "scope_task_id": proposal.scope_task_id,
    })
    create_agent_run(ctx)
    with execution_context(ctx):
        result = request_plan_confirmation(proposal_id)
    status = 200 if result["success"] else 400
    return jsonify(result["data"] if result["success"] else {"error": result["error"]}), status


@plan_bp.route("/plans/<proposal_id>/apply", methods=["POST"])
@jwt_required()
def apply_plan(proposal_id):
    proposal = db.session.get(PlanProposal, proposal_id)
    if not proposal:
        return jsonify({"error": "PlanProposal not found"}), 404
    data = request.json or {}
    ctx = _ctx(proposal.workspace_id, run_id=str(uuid.uuid4()), scope={
        "scope_level": proposal.scope_level,
        "scope_project_id": proposal.scope_project_id,
        "scope_task_id": proposal.scope_task_id,
    })
    create_agent_run(ctx)
    with execution_context(ctx):
        result = apply_plan_proposal(proposal_id, approved=bool(data.get("approved", True)))
    status = 200 if result["success"] or result["data"] else 400
    return jsonify(result["data"] if result["data"] else {"error": result["error"]}), status
