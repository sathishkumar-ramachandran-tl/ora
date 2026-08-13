"""
Legacy one-shot AI endpoints — direct google-genai prompt->JSON calls (app/agents/legacy_ai_service.py),
not the LangGraph orchestrator. Kept for the frontend features that still call them
(AI task generation dialog fallback, voice assistant, schedule optimizer) but not the
main agentic surface — that's app/agents/orchestrator.py + app/api/chat.py.
"""
import asyncio
import base64
import logging
import uuid
from datetime import datetime

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func

from .legacy_ai_service import AIService
from .execution_context import ExecutionContext, execution_context
from .models import AgentAction, AgentRun, LlmCall
from .undo import undo_action
from ..core.extensions import db
from ..workspaces.models import WorkspaceMember

logger = logging.getLogger(__name__)
agent_bp = Blueprint('agent', __name__)


@agent_bp.route('/actions/<action_id>/undo', methods=['POST'])
@jwt_required()
def undo_agent_action(action_id):
    action = db.session.get(AgentAction, action_id)
    if not action:
        return jsonify({"error": "Action not found"}), 404
    run = db.session.get(AgentRun, action.run_id)
    user_id = get_jwt_identity()
    if not run:
        return jsonify({"error": "Agent run not found"}), 404
    from ..core.authz import user_can_access_workspace
    if not user_can_access_workspace(user_id, run.workspace_id):
        return jsonify({"error": "Forbidden"}), 403
    ctx = ExecutionContext(
        request_id=str(uuid.uuid4()),
        user_id=user_id,
        workspace_id=run.workspace_id,
        session_id=run.session_id,
        run_id=run.id,
    )
    with execution_context(ctx):
        result = undo_action(action_id)
    return jsonify(result["data"] if result["success"] else {"error": result["error"]}), 200 if result["success"] else 409


@agent_bp.route('/llm-usage', methods=['GET'])
@jwt_required()
def llm_usage():
    """Token-usage / cost ledger for a workspace — the observability surface over
    LlmCall rows written by app/agents/llm_tracking.py on every orchestrator LLM call."""
    user_id = get_jwt_identity()
    workspace_id = request.args.get('workspace_id') or request.args.get('workspaceId')
    if not workspace_id:
        return jsonify({"error": "workspace_id required"}), 400

    is_member = WorkspaceMember.query.filter_by(
        workspace_id=workspace_id, user_id=user_id
    ).first() is not None
    if not is_member:
        return jsonify({"error": "Not a member of this workspace"}), 403

    totals = db.session.query(
        func.coalesce(func.sum(LlmCall.prompt_tokens), 0),
        func.coalesce(func.sum(LlmCall.completion_tokens), 0),
        func.coalesce(func.sum(LlmCall.total_tokens), 0),
        func.coalesce(func.sum(LlmCall.estimated_cost_usd), 0.0),
        func.count(LlmCall.id),
    ).filter(LlmCall.workspace_id == workspace_id).one()

    by_model = db.session.query(
        LlmCall.model,
        func.count(LlmCall.id),
        func.coalesce(func.sum(LlmCall.total_tokens), 0),
        func.coalesce(func.sum(LlmCall.estimated_cost_usd), 0.0),
    ).filter(LlmCall.workspace_id == workspace_id).group_by(LlmCall.model).all()

    recent = LlmCall.query.filter_by(workspace_id=workspace_id) \
        .order_by(LlmCall.created_at.desc()).limit(50).all()

    return jsonify({
        "totals": {
            "promptTokens": totals[0],
            "completionTokens": totals[1],
            "totalTokens": totals[2],
            "estimatedCostUsd": round(totals[3], 6),
            "callCount": totals[4],
        },
        "byModel": [
            {"model": m, "callCount": c, "totalTokens": t, "estimatedCostUsd": round(cost, 6)}
            for m, c, t, cost in by_model
        ],
        "recent": [
            {
                "id": r.id,
                "sessionId": r.session_id,
                "node": r.node,
                "model": r.model,
                "promptTokens": r.prompt_tokens,
                "completionTokens": r.completion_tokens,
                "totalTokens": r.total_tokens,
                "estimatedCostUsd": r.estimated_cost_usd,
                "latencyMs": r.latency_ms,
                "status": r.status,
                "createdAt": r.created_at.isoformat() if r.created_at else None,
            }
            for r in recent
        ],
    })


@agent_bp.route('/generate-plan', methods=['POST'])
@jwt_required()
def generate_plan():
    data = request.json or {}
    service = AIService()
    tasks = service.generate_project_plan(
        data['project'], data['companyMission'], data['userGuidance'], data['persona']
    )
    return jsonify({"tasks": tasks})


@agent_bp.route('/executive-summary', methods=['POST'])
@jwt_required()
def exec_summary():
    data = request.json or {}
    service = AIService()
    result = service.generate_summary(data['companies'], data['persona'])
    return jsonify(result)


@agent_bp.route('/scheduler-advice', methods=['POST'])
@jwt_required()
def scheduler_advice():
    data = request.json or {}
    service = AIService()
    advice = service.generate_schedule(data['companies'], data['persona'])
    return jsonify({"advice": advice})


@agent_bp.route('/voice', methods=['POST'])
@jwt_required()
def voice_session():
    """Voice endpoint using the Gemini Live API. Frontend sends base64 audio, receives base64 audio back."""
    try:
        from google import genai
        from google.genai import types as gtypes

        data = request.json or {}
        persona = data.get('persona', 'general')
        audio_data = data.get('audio', '')
        if not audio_data:
            return jsonify({"error": "Audio data required"}), 400

        api_key = current_app.config.get('API_KEY')
        if not api_key:
            return jsonify({"error": "Gemini API key not configured"}), 500

        client = genai.Client(api_key=api_key, http_options={"api_version": "v1alpha"})
        live_config = gtypes.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=gtypes.SpeechConfig(
                voice_config=gtypes.VoiceConfig(
                    prebuilt_voice_config=gtypes.PrebuiltVoiceConfig(voice_name="Kore")
                )
            ),
            system_instruction=gtypes.Content(parts=[gtypes.Part(text=(
                f"You are Ora, an intelligent Executive Chief of Staff for a {persona}. "
                "Be concise, extremely sharp, and action-oriented."
            ))]),
        )

        response_audio = None

        async def _run_live():
            nonlocal response_audio
            async with client.aio.live.connect(model="gemini-2.0-flash-live-001", config=live_config) as session:
                await session.send_realtime_input(
                    audio=gtypes.Blob(data=base64.b64decode(audio_data), mime_type="audio/pcm;rate=16000")
                )
                async for msg in session.receive():
                    if (msg.server_content and msg.server_content.model_turn
                            and msg.server_content.model_turn.parts):
                        for part in msg.server_content.model_turn.parts:
                            if part.inline_data:
                                response_audio = base64.b64encode(part.inline_data.data).decode("utf-8")
                                return

        asyncio.run(_run_live())
        return jsonify({"audio": response_audio, "status": "success"})

    except Exception as e:
        logger.error("Voice session error", extra={"error": str(e)})
        return jsonify({"error": str(e)}), 500


@agent_bp.route('/optimize-schedule', methods=['POST'])
@jwt_required()
def optimize_schedule():
    data = request.json or {}
    tasks = data.get('tasks', [])
    date_str = data.get('date')

    service = AIService()
    suggested_slots = service.optimize_daily_schedule(tasks, date_str)

    final_events = []
    base_date = datetime.fromisoformat(date_str) if date_str else datetime.now()

    for slot in suggested_slots:
        try:
            start_parts = slot['start'].split(':')
            end_parts = slot['end'].split(':')
            start_dt = base_date.replace(hour=int(start_parts[0]), minute=int(start_parts[1]), second=0)
            end_dt = base_date.replace(hour=int(end_parts[0]), minute=int(end_parts[1]), second=0)

            final_events.append({
                "title": slot['title'], "start": start_dt.isoformat(), "end": end_dt.isoformat(),
                "type": slot['type'], "taskId": slot.get('taskId'),
                "scope": 'personal', "isAutoGenerated": True,
            })
        except Exception as e:
            logger.error("Slot parsing error", extra={"error": str(e)})
            continue

    return jsonify(final_events)
