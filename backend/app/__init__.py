import logging
from flask import Flask, jsonify, request, make_response
from werkzeug.middleware.proxy_fix import ProxyFix
from .config import Config
from .extensions import db, migrate, jwt, cors, mail
from .routes import auth_bp, workspace_bp, agent_bp
from .api.org import org_bp
from .api.workspace import workspace_api_bp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # ProxyFix for Cloud Run (HTTPS termination)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    cors.init_app(app,
        resources={r"/*": {
            "origins": [
                "https://sindhai.teams-lab.com",
                "https://gen-lang-client-0256042453.web.app",
                "http://localhost:5173",
                "http://localhost:3000"
            ],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
            "allow_headers": ["Content-Type", "Authorization", "X-Requested-With", "Accept", "Origin"],
            "supports_credentials": True,
            "max_age": 3600
        }}
    )

    mail.init_app(app)

    # Register v1 Blueprints
    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
    app.register_blueprint(workspace_bp, url_prefix='/api/v1')
    app.register_blueprint(agent_bp, url_prefix='/api/v1/agents')

    # Register v2 Enterprise Routes
    app.register_blueprint(org_bp, url_prefix='/api/v2/orgs')
    app.register_blueprint(workspace_api_bp, url_prefix='/api/v2/workspaces')

    # Register Agentic Chat Routes (v1/chat)
    from .api.chat import chat_bp
    app.register_blueprint(chat_bp, url_prefix='/api/v1/chat')

    # -----------------------------------------------------------------------
    # A2A (Agent-to-Agent) Protocol Endpoints
    # Follows Google's A2A spec: https://google.github.io/A2A
    # -----------------------------------------------------------------------
    import uuid as _uuid
    from datetime import datetime

    @app.route('/.well-known/agent.json')
    def agent_card():
        """A2A Agent Card — describes this agent's capabilities to peers."""
        return jsonify({
            "@context": "https://schema.org/",
            "@type": "AgentCard",
            "name": "Sindhai Cortex",
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
                "description": "JWT token from POST /api/v1/auth/verify-otp"
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

        # Delegate to the orchestrator synchronously
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
        except Exception as e:
            response_text = f"Agent error: {e}"

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
            "message": "Sindhai processes tasks synchronously. Check /a2a/tasks/send response."
        })

    @app.route('/health')
    def health_check():
        return jsonify({
            "status": "healthy",
            "service": "Sindhai-Cortex",
            "version": "2.0.0",
            "agents": ["orchestrator", "query", "crud", "planning", "analysis"],
            "protocols": ["REST", "SSE", "MCP", "A2A"]
        })

    # Ensure tables exist (auto-create for MVP)
    with app.app_context():
        db.create_all()

    return app
