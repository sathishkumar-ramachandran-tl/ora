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

from flask import Blueprint, request, jsonify, Response, stream_with_context
from flask_jwt_extended import jwt_required, get_jwt_identity
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, AIMessageChunk

from ..core.extensions import db
from ..workspaces.models import Workspace, WorkspaceMember
from ..projects.models import Company, Project
from ..tasks.models import Task
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
        "createdAt": session.created_at.isoformat(),
        "updatedAt": session.updated_at.isoformat() if session.updated_at else session.created_at.isoformat()
    }


def _message_to_dict(msg: ChatMessage) -> dict:
    return {
        "id": msg.id,
        "sessionId": msg.session_id,
        "role": msg.role,
        "content": msg.content,
        "metadata": msg.metadata_ or {},
        "createdAt": msg.created_at.isoformat()
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

    context = _build_workspace_context(workspace_id)
    session = ChatSession(
        workspace_id=workspace_id,
        user_id=user_id,
        title=data.get("title", "New Conversation"),
        context=context
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
        session.workspace_id = workspace_id

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
            orchestrator = create_orchestrator()

            # Rebuild workspace context (may have changed since session created)
            ws_ctx = _build_workspace_context(session.workspace_id or "")

            # Load prior messages to restore conversation history
            prior_messages = ChatMessage.query.filter_by(
                session_id=session_id
            ).order_by(ChatMessage.created_at.asc()).all()

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

            # Stream from LangGraph
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
            logger.error(f"Agent streaming error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        finally:
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
