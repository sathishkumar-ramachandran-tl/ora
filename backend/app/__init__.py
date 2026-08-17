import os
import uuid as _uuid
from datetime import datetime

from flask import Flask, jsonify, request
from werkzeug.middleware.proxy_fix import ProxyFix

from .core.config import Config
from .core.extensions import db, migrate, jwt, cors
from .core.logging import configure_logging
from .core.rate_limit import check_rate_limit
from .auth.oauth import init_oauth

from .auth.routes import auth_bp
from .organizations.routes import org_bp
from .workspaces.routes import workspace_bp
from .projects.routes import project_bp
from .tasks.routes import task_bp
from .notes.routes import note_bp
from .documents.routes import document_bp
from .calendar.routes import calendar_bp
from .analytics.routes import analytics_bp
from .agents.legacy_routes import agent_bp
from .agents.plan_routes import plan_bp
from .chat.routes import chat_bp
from .billing.routes import billing_bp
from .modules.routes import module_bp
from .payments.routes import payments_bp

# Import every domain's models so they're registered on db.metadata before
# db.create_all()/Alembic run, regardless of which blueprint imports first.
from . import models  # noqa: F401


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    configure_logging(app)

    # ProxyFix for Cloud Run (HTTPS termination)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    init_oauth(app)

    cors.init_app(
        app,
        resources={r"/*": {
            "origins": app.config["CORS_ALLOWED_ORIGINS"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
            "allow_headers": ["Content-Type", "Authorization", "X-Requested-With", "Accept", "Origin"],
            "supports_credentials": True,
            "max_age": 3600
        }}
    )

    @app.before_request
    def enforce_rate_limits():
        return check_rate_limit()

    @app.after_request
    def apply_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
        )
        if request.is_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    # --- v1 blueprints ---
    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
    app.register_blueprint(workspace_bp, url_prefix='/api/v1')
    app.register_blueprint(project_bp, url_prefix='/api/v1')
    app.register_blueprint(task_bp, url_prefix='/api/v1')
    app.register_blueprint(note_bp, url_prefix='/api/v1')
    app.register_blueprint(document_bp, url_prefix='/api/v1')
    app.register_blueprint(calendar_bp, url_prefix='/api/v1')
    app.register_blueprint(analytics_bp, url_prefix='/api/v1')
    app.register_blueprint(agent_bp, url_prefix='/api/v1/agents')
    app.register_blueprint(plan_bp, url_prefix='/api/v1')
    app.register_blueprint(chat_bp, url_prefix='/api/v1/chat')

    # --- v2 blueprints (enterprise/org surface) ---
    app.register_blueprint(org_bp, url_prefix='/api/v2/orgs')
    app.register_blueprint(billing_bp, url_prefix='/api/v2/billing')
    app.register_blueprint(module_bp, url_prefix='/api/v2/modules')
    app.register_blueprint(payments_bp, url_prefix='/api/v2/payments')

    # -----------------------------------------------------------------------
    # A2A (Agent-to-Agent) Protocol Endpoints
    # Follows Google's A2A spec: https://google.github.io/A2A
    # -----------------------------------------------------------------------

    @app.route('/.well-known/agent.json')
    def agent_card():
        """A2A Agent Card — describes this agent's capabilities to peers."""
        return jsonify({
            "@context": "https://schema.org/",
            "@type": "AgentCard",
            "name": "Ora Cortex",
            "description": "AI-native OS for project and learning management. Supports CRUD, analysis, and multi-turn planning.",
            "url": request.host_url.rstrip('/'),
            "version": "2.0.0",
            "capabilities": [
                "task_management", "project_planning", "workspace_analysis",
                "multi_turn_conversation", "schedule_optimization"
            ],
            "skills": [
                {
                    "id": "crud",
                    "name": "CRUD Operations",
                    "description": "Create, update, and delete tasks, projects, and initiatives.",
                    "examples": ["create a task for X", "mark task Y as done", "delete project Z"]
                },
                {
                    "id": "query",
                    "name": "Workspace Query",
                    "description": "Query workspace data: list tasks, get project status, search.",
                    "examples": ["list all high priority tasks", "show me in-progress items"]
                },
                {
                    "id": "plan",
                    "name": "Multi-turn Planning",
                    "description": "Interactive multi-turn project planning with clarification and refinement.",
                    "examples": ["help me plan a product launch", "plan my research project"]
                },
                {
                    "id": "analyze",
                    "name": "Strategic Analysis",
                    "description": "Deep analysis of workspace with prioritization and risk identification.",
                    "examples": ["analyze my workspace", "what should I focus on this week"]
                }
            ],
            "authentication": {
                "type": "Bearer",
                "description": "JWT token from POST /api/v1/auth/login"
            },
            "endpoints": {
                "chat": "/api/v1/chat/sessions",
                "tasks": "/api/v1/chat/sessions/{id}/messages",
                "a2a_tasks": "/a2a/tasks/send"
            }
        })

    @app.route('/a2a/tasks/send', methods=['POST'])
    def a2a_receive_task():
        """
        A2A task receiver — accepts task delegation from peer agents.
        Body: { "id": "...", "message": { "role": "user", "parts": [{"text": "..."}] },
                "metadata": { "workspace_id": "..." } }
        """
        from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
        try:
            verify_jwt_in_request()
            user_id = get_jwt_identity()
        except Exception:
            return jsonify({"error": "Authentication required"}), 401

        data = request.json or {}
        task_id = data.get("id") or str(_uuid.uuid4())
        message_parts = data.get("message", {}).get("parts", [])
        text = " ".join(p.get("text", "") for p in message_parts if "text" in p)
        workspace_id = data.get("metadata", {}).get("workspace_id", "")

        if not text:
            return jsonify({"error": "No message text provided"}), 400
        if not workspace_id:
            return jsonify({"error": "workspace_id is required"}), 400

        from .core.authz import user_can_access_workspace
        if not user_can_access_workspace(user_id, workspace_id):
            return jsonify({"error": "Forbidden"}), 403

        try:
            from .agents.orchestrator import create_orchestrator
            from langchain_core.messages import HumanMessage

            orchestrator = create_orchestrator()
            state = {
                "messages": [HumanMessage(content=text)],
                "workspace_id": workspace_id,
                "user_id": user_id,
                "workspace_context": {},
                "intent": None,
                "planning_phase": None,
                "draft_plan": {},
                "planning_project_id": None
            }
            config = {"configurable": {"thread_id": f"a2a_{task_id}"}}
            result = orchestrator.invoke(state, config=config)
            last_msg = result["messages"][-1]
            response_text = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
        except Exception:
            app.logger.exception("a2a_task_failed", extra={"task_id": task_id, "workspace_id": workspace_id})
            return jsonify({"error": "Agent task failed"}), 500

        return jsonify({
            "id": task_id,
            "status": {"state": "completed"},
            "result": {
                "message": {
                    "role": "agent",
                    "parts": [{"text": response_text}]
                }
            }
        })

    @app.route('/a2a/tasks/<task_id>', methods=['GET'])
    def a2a_get_task(task_id):
        """A2A task status — for polling task completion."""
        return jsonify({
            "id": task_id,
            "status": {"state": "completed"},
            "message": "Ora processes tasks synchronously. Check /a2a/tasks/send response."
        })

    @app.errorhandler(Exception)
    def handle_uncaught_exception(e):
        """Last-resort net — guarantees every 500 is logged with a stack trace and
        request_id before the client sees a generic error, instead of surfacing
        Flask's default unlogged HTML traceback page."""
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return e
        app.logger.error(
            "unhandled_exception",
            exc_info=e,
            extra={"method": request.method, "path": request.path},
        )
        return jsonify({"error": "Internal server error"}), 500

    @app.route('/health')
    def health_check():
        return jsonify({
            "status": "healthy",
            "service": "Ora-Cortex",
            "version": "2.0.0",
            "agents": ["orchestrator", "query", "crud", "planning", "analysis"],
            "protocols": ["REST", "SSE", "MCP", "A2A"]
        })

    # Auto-create missing tables for zero-config dev (MVP convenience).
    # Disable via AUTO_CREATE_TABLES=false when schema should come from Alembic
    # migrations only (e.g. generating/testing migrations, or a hardened prod boot).
    if app.config.get('AUTO_CREATE_TABLES'):
        with app.app_context():
            db.create_all()

    # Idempotent — inserts the 5 launch plans if the table is empty, never
    # overwrites limits an admin has already tuned.
    with app.app_context():
        try:
            from .billing.service import seed_plans
            seed_plans()
        except Exception as e:
            app.logger.warning(f"Billing plan seed skipped: {e}")

    # Idempotent — inserts the demo capability-provider catalog only for capabilities
    # that have no providers registered yet, so the Agent Economy has something to
    # discover/select from out of the box.
    with app.app_context():
        try:
            from .payments.discovery import seed_default_providers
            seed_default_providers()
        except Exception as e:
            app.logger.warning(f"Capability provider seed skipped: {e}")

    return app
