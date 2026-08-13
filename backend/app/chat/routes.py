"""
Chat API — SSE streaming endpoint for the Ora Agentic Chat.

POST /api/v1/chat/sessions              — create session
GET  /api/v1/chat/sessions              — list user's sessions
GET  /api/v1/chat/sessions/<id>         — get session + messages
POST /api/v1/chat/sessions/<id>/messages — send message (SSE stream)
DELETE /api/v1/chat/sessions/<id>       — delete session
"""
import json
import uuid
import logging
from datetime import datetime

from flask import Blueprint, request, jsonify, Response, stream_with_context, g
from flask_jwt_extended import jwt_required, get_jwt_identity
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, AIMessageChunk

from ..core.extensions import db
from ..workspaces.models import Workspace, WorkspaceMember
from ..projects.models import Company, Project
from ..tasks.models import Task
from ..agents.action_executor import create_agent_run
from ..agents.context import build_context_envelope
from ..agents.control_plane import AgentRunStatus
from ..agents.execution_context import ExecutionContext, execution_context
from ..agents.models import AgentAction, AgentRun, ScheduleProposal
from ..agents.planning import create_plan_proposal, serialize_plan, should_create_plan_proposal
from ..agents.scheduling import create_schedule_proposal, serialize_schedule, should_create_schedule_proposal
from .models import ChatSession, ChatMessage


def _extract_text(content) -> str:
    """Normalize Gemini content which may be a str or list of content parts."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return ''.join(
            part.get('text', '') if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content) if content else ''

logger = logging.getLogger(__name__)
chat_bp = Blueprint("chat", __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_workspace_context(workspace_id: str) -> dict:
    """Lightweight snapshot injected into every agent call for grounding."""
    workspace = db.session.get(Workspace, workspace_id)
    if not workspace:
        return {}

    companies = Company.query.filter_by(workspace_id=workspace_id).all()
    context = {
        "workspace_id": workspace_id,
        "workspace_name": workspace.name,
        "persona": workspace.persona,
        "initiatives": []
    }
    for c in companies:
        projects = Project.query.filter_by(company_id=c.id).all()
        ctx_projects = []
        for p in projects:
            task_count = Task.query.filter_by(project_id=p.id).count()
            ctx_projects.append({
                "id": p.id,
                "name": p.name,
                "type": p.type,
                "task_count": task_count
            })
        context["initiatives"].append({
            "id": c.id,
            "name": c.name,
            "mission": c.mission,
            "projects": ctx_projects
        })
    return context


def _session_to_dict(session: ChatSession) -> dict:
    return {
        "id": session.id,
        "title": session.title,
        "workspaceId": session.workspace_id,
        "scopeLevel": session.scope_level or "workspace",
        "scopeProjectId": session.scope_project_id,
        "scopeTaskId": session.scope_task_id,
        "createdAt": session.created_at.isoformat(),
        "updatedAt": session.updated_at.isoformat() if session.updated_at else session.created_at.isoformat()
    }


def _validate_scope(
    workspace_id: str,
    scope_level: str | None = "workspace",
    scope_project_id: str | None = None,
    scope_task_id: str | None = None,
) -> tuple[dict | None, tuple]:
    level = scope_level or "workspace"
    if level not in {"workspace", "project", "task"}:
        return None, (jsonify({"error": "Invalid scope_level"}), 400)

    project_id = scope_project_id
    task_id = scope_task_id

    if level == "project":
        if not project_id:
            return None, (jsonify({"error": "scope_project_id required for project scope"}), 400)
        project = db.session.get(Project, project_id)
        if not project or project.workspace_id != workspace_id:
            return None, (jsonify({"error": "Scoped project not found"}), 404)

    if level == "task":
        if not task_id:
            return None, (jsonify({"error": "scope_task_id required for task scope"}), 400)
        task = db.session.get(Task, task_id)
        if not task or task.workspace_id != workspace_id:
            return None, (jsonify({"error": "Scoped task not found"}), 404)
        project_id = project_id or task.project_id
        if project_id and project_id != task.project_id:
            return None, (jsonify({"error": "Scoped task/project mismatch"}), 400)

    if level == "workspace":
        project_id = None
        task_id = None

    return {
        "scope_level": level,
        "scope_project_id": project_id,
        "scope_task_id": task_id,
    }, None


def _message_to_dict(msg: ChatMessage) -> dict:
    return {
        "id": msg.id,
        "sessionId": msg.session_id,
        "role": msg.role,
        "content": msg.content,
        "metadata": msg.metadata_ or {},
        "createdAt": msg.created_at.isoformat()
    }


def _action_event(action: AgentAction) -> dict:
    event_type = {
        "WAITING_FOR_CONFIRMATION": "confirmation_required",
        "SUCCEEDED": "action_completed",
        "FAILED": "action_failed",
        "UNKNOWN": "action_failed",
        "RUNNING": "action_started",
        "PROPOSED": "action_proposed",
    }.get(action.status, "action_updated")
    return {
        "type": event_type,
        "action": {
            "id": action.id,
            "runId": action.run_id,
            "actionType": action.action_type,
            "resourceType": action.resource_type,
            "resourceId": action.resource_id,
            "status": action.status,
            "riskLevel": action.risk_level,
            "confirmationRequired": action.confirmation_required,
            "reversible": action.reversible,
            "undoStatus": action.undo_status,
            "undoActionId": action.undo_action_id,
            "proposedArgs": action.proposed_args or {},
            "afterState": action.after_state or {},
        }
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@chat_bp.route("/sessions", methods=["POST"])
@jwt_required()
def create_session():
    user_id = get_jwt_identity()
    data = request.json or {}
    workspace_id = data.get("workspace_id") or data.get("workspaceId")

    if not workspace_id:
        return jsonify({"error": "workspace_id required"}), 400

    # Check membership
    member = WorkspaceMember.query.filter_by(
        workspace_id=workspace_id, user_id=user_id
    ).first()
    if not member:
        return jsonify({"error": "Access denied"}), 403

    scope, scope_error = _validate_scope(
        workspace_id,
        data.get("scope_level") or data.get("scopeLevel") or "workspace",
        data.get("scope_project_id") or data.get("scopeProjectId"),
        data.get("scope_task_id") or data.get("scopeTaskId"),
    )
    if scope_error:
        return scope_error

    context = _build_workspace_context(workspace_id)
    session = ChatSession(
        workspace_id=workspace_id,
        user_id=user_id,
        title=data.get("title", "New Conversation"),
        context=context,
        **scope,
    )
    db.session.add(session)
    db.session.commit()

    return jsonify(_session_to_dict(session)), 201


@chat_bp.route("/sessions", methods=["GET"])
@jwt_required()
def list_sessions():
    user_id = get_jwt_identity()
    workspace_id = request.args.get("workspace_id") or request.args.get("workspaceId")

    q = ChatSession.query.filter_by(user_id=user_id)
    if workspace_id:
        q = q.filter_by(workspace_id=workspace_id)

    sessions = q.order_by(ChatSession.updated_at.desc()).limit(20).all()
    return jsonify([_session_to_dict(s) for s in sessions])


@chat_bp.route("/sessions/<session_id>", methods=["GET"])
@jwt_required()
def get_session(session_id):
    user_id = get_jwt_identity()
    session = db.session.get(ChatSession, session_id)

    if not session or session.user_id != user_id:
        return jsonify({"error": "Session not found"}), 404

    messages = ChatMessage.query.filter_by(session_id=session_id).order_by(
        ChatMessage.created_at.asc()
    ).all()

    return jsonify({
        **_session_to_dict(session),
        "messages": [_message_to_dict(m) for m in messages]
    })


@chat_bp.route("/sessions/<session_id>", methods=["DELETE"])
@jwt_required()
def delete_session(session_id):
    user_id = get_jwt_identity()
    session = db.session.get(ChatSession, session_id)

    if not session or session.user_id != user_id:
        return jsonify({"error": "Session not found"}), 404

    db.session.delete(session)
    db.session.commit()
    return jsonify({"status": "deleted"})


@chat_bp.route("/sessions/<session_id>/messages", methods=["POST"])
@jwt_required()
def send_message(session_id):
    """
    SSE streaming endpoint. Accepts:
    { "content": "user message text", "workspace_id": "..." }

    Streams back:
    data: {"type": "chunk", "content": "...", "node": "query_agent"}\n\n
    data: {"type": "tool_call", "name": "get_tasks", "status": "running"}\n\n
    data: {"type": "tool_result", "name": "get_tasks", "result": {...}}\n\n
    data: {"type": "done", "message_id": "..."}\n\n
    data: {"type": "error", "message": "..."}\n\n
    """
    user_id = get_jwt_identity()
    data = request.json or {}
    content = data.get("content", "").strip()
    workspace_id = data.get("workspace_id") or data.get("workspaceId")

    if not content:
        return jsonify({"error": "content required"}), 400

    session = db.session.get(ChatSession, session_id)
    if not session or session.user_id != user_id:
        return jsonify({"error": "Session not found"}), 404

    if workspace_id:
        member = WorkspaceMember.query.filter_by(
            workspace_id=workspace_id, user_id=user_id
        ).first()
        if not member:
            return jsonify({"error": "Access denied"}), 403
        session.workspace_id = workspace_id

    scope, scope_error = _validate_scope(
        session.workspace_id,
        data.get("scope_level") or data.get("scopeLevel") or session.scope_level or "workspace",
        data.get("scope_project_id") or data.get("scopeProjectId") or session.scope_project_id,
        data.get("scope_task_id") or data.get("scopeTaskId") or session.scope_task_id,
    )
    if scope_error:
        return scope_error
    session.scope_level = scope["scope_level"]
    session.scope_project_id = scope["scope_project_id"]
    session.scope_task_id = scope["scope_task_id"]

    request_id = getattr(g, "request_id", None) or str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    trusted_ctx = ExecutionContext(
        request_id=request_id,
        user_id=user_id,
        workspace_id=session.workspace_id,
        session_id=session_id,
        run_id=run_id,
        scope_level=session.scope_level or "workspace",
        scope_project_id=session.scope_project_id,
        scope_task_id=session.scope_task_id,
    )
    create_agent_run(trusted_ctx)

    # Persist user message
    user_msg = ChatMessage(
        session_id=session_id,
        role="user",
        content=content
    )
    db.session.add(user_msg)
    db.session.commit()

    # Auto-name session from first message
    if session.title == "New Conversation":
        session.title = content[:60] + ("…" if len(content) > 60 else "")
        db.session.commit()

    def generate():
        import os

        # AGENT_ENGINE=v2 (default) uses the Core Intelligence Layer's recursive
        # plan/act/reflect graph (agents/graph_v2.py). Set AGENT_ENGINE=v1 to fall back
        # to the original single-hop router->one-agent orchestrator while v2 is being
        # validated in production.
        engine = os.environ.get("AGENT_ENGINE", "v2")
        if engine == "v1":
            from ..agents.orchestrator import create_orchestrator
        else:
            from ..agents.graph_v2 import create_orchestrator

        full_response = []
        assistant_msg_id = str(uuid.uuid4())

        try:
            yield f"data: {json.dumps({'type': 'agent_run_started', 'runId': run_id})}\n\n"

            if should_create_plan_proposal(content):
                with execution_context(trusted_ctx):
                    proposal = create_plan_proposal(trusted_ctx, content)
                plan_data = serialize_plan(proposal)
                yield f"data: {json.dumps({'type': 'plan_proposed', 'plan': plan_data})}\n\n"
                summary = plan_data["summary"]
                full_response.append(
                    f"Plan proposed: {plan_data['title']} "
                    f"({summary['phaseCount']} phases, {summary['taskCount']} tasks). Review it before applying."
                )
                return

            if should_create_schedule_proposal(content):
                with execution_context(trusted_ctx):
                    proposal = create_schedule_proposal(
                        trusted_ctx,
                        project_id=trusted_ctx.scope_project_id,
                        title="This week's schedule",
                    )
                schedule_data = serialize_schedule(proposal)
                yield f"data: {json.dumps({'type': 'schedule_proposed', 'schedule': schedule_data})}\n\n"
                full_response.append(
                    f"Schedule proposed: {schedule_data['summary'].get('sessionCount', 0)} sessions. "
                    "Review it before applying."
                )
                return

            orchestrator = create_orchestrator()

            # Load prior messages to restore conversation history
            prior_messages = ChatMessage.query.filter_by(
                session_id=session_id
            ).order_by(ChatMessage.created_at.asc()).all()
            ws_ctx = build_context_envelope(trusted_ctx, recent_messages=prior_messages)

            lc_messages = []
            for m in prior_messages:
                if m.role == "user":
                    lc_messages.append(HumanMessage(content=m.content or ""))
                elif m.role == "assistant":
                    lc_messages.append(AIMessage(content=m.content or ""))

            base_state = {
                "messages": lc_messages,
                "workspace_id": session.workspace_id or "",
                "user_id": user_id,
                "workspace_context": ws_ctx,
                "planning_phase": None,
                "draft_plan": {},
                "planning_project_id": None,
            }

            if engine == "v1":
                initial_state = {**base_state, "intent": None}
                config = {"configurable": {"thread_id": session_id}, "recursion_limit": 20}
            else:
                initial_state = {
                    **base_state,
                    "complexity": None,
                    "goal": None,
                    "plan": [],
                    "working_memory": {},
                    "current_step_index": 0,
                    "replan_count": 0,
                    "next_action": None,
                    "final_answer": None,
                }
                # Recursive plan/act/reflect steps consume more graph transitions than
                # v1's single hop — headroom for a full plan + bounded replans.
                config = {"configurable": {"thread_id": session_id}, "recursion_limit": 50}

            # Stream from LangGraph with trusted identity/scope available to all tools.
            with execution_context(trusted_ctx):
                for event in orchestrator.stream(
                    initial_state,
                    config=config,
                    stream_mode="messages"
                ):
                    if isinstance(event, tuple):
                        msg_chunk, metadata = event
                        node = metadata.get("langgraph_node", "")
                        msg_type = getattr(msg_chunk, "type", "")

                        # Only stream text from AI response messages — never from
                        # SystemMessage, HumanMessage, or ToolMessage. Those carry
                        # internal plumbing that must not appear in the chat bubble.
                        is_ai = isinstance(msg_chunk, AIMessageChunk) or msg_type == "ai"

                        # Only emit text from the final response — not from mid-reasoning
                        # messages that also carry tool_calls (those would leak "let me query..."
                        # thinking text into the chat bubble).
                        has_tool_calls = bool(getattr(msg_chunk, 'tool_calls', None))
                        if is_ai and not has_tool_calls and hasattr(msg_chunk, "content") and msg_chunk.content:
                            chunk_text = _extract_text(msg_chunk.content)
                            if chunk_text:
                                full_response.append(chunk_text)
                                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk_text, 'node': node})}\n\n"

                        # Tool call initiated by AI (show as pill in UI)
                        if is_ai and has_tool_calls:
                            for tc in msg_chunk.tool_calls:
                                yield f"data: {json.dumps({'type': 'tool_call', 'name': tc.get('name', ''), 'status': 'running'})}\n\n"

                        # Tool result returned (show as pill update — never as chat text)
                        if msg_type == "tool" and hasattr(msg_chunk, "name"):
                            raw_content = _extract_text(msg_chunk.content)
                            try:
                                result_data = json.loads(raw_content)
                            except Exception:
                                result_data = raw_content
                            yield f"data: {json.dumps({'type': 'tool_result', 'name': msg_chunk.name, 'result': result_data})}\n\n"

        except Exception as e:
            run = db.session.get(AgentRun, run_id)
            if run:
                run.status = AgentRunStatus.FAILED.value
                run.completed_at = datetime.utcnow()
                run.error_message = str(e)
                db.session.commit()
            logger.error(f"Agent streaming error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        finally:
            run = db.session.get(AgentRun, run_id)
            if run and run.status == AgentRunStatus.RUNNING.value:
                run.status = AgentRunStatus.COMPLETED.value
                run.completed_at = datetime.utcnow()
                db.session.commit()

            actions = AgentAction.query.filter_by(run_id=run_id).order_by(AgentAction.created_at.asc()).all()
            for action in actions:
                yield f"data: {json.dumps(_action_event(action), default=str)}\n\n"
            schedules = ScheduleProposal.query.filter_by(run_id=run_id).order_by(ScheduleProposal.created_at.asc()).all()
            for schedule in schedules:
                event_type = "schedule_applied" if schedule.status in {"APPLIED", "PARTIALLY_APPLIED"} else "schedule_proposed"
                yield f"data: {json.dumps({'type': event_type, 'schedule': serialize_schedule(schedule)}, default=str)}\n\n"
            run = db.session.get(AgentRun, run_id)
            if run:
                yield f"data: {json.dumps({'type': 'agent_run_completed', 'runId': run_id, 'status': run.status})}\n\n"

            # Persist completed assistant message
            final_content = "".join(str(p) for p in full_response)
            if final_content:
                asst_msg = ChatMessage(
                    id=assistant_msg_id,
                    session_id=session_id,
                    role="assistant",
                    content=final_content
                )
                db.session.add(asst_msg)
                session.updated_at = datetime.utcnow()
                db.session.commit()

            yield f"data: {json.dumps({'type': 'done', 'message_id': assistant_msg_id})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*"
        }
    )
