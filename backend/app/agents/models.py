import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from ..core.extensions import db


def generate_uuid():
    return str(uuid.uuid4())


class AgentToolCall(db.Model):
    """Audit log of every tool invocation, written from the single choke point in
    app/tools/ so both the LangGraph orchestrator and the MCP server log identically."""
    __tablename__ = 'agent_tool_calls'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    session_id = db.Column(db.String, nullable=True)  # chat_sessions.id or MCP session ref
    tool_name = db.Column(db.String, nullable=False)
    tool_args = db.Column(JSONB, default=dict)
    tool_result = db.Column(JSONB, default=dict)  # {success, data, error}
    status = db.Column(db.String, default='success')  # success|error
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'), nullable=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=True)


class PlanningSession(db.Model):
    """Durable multi-turn planning state — replaces the heuristic response-text-keyword
    phase inference previously done ad hoc inside the planning agent node."""
    __tablename__ = 'planning_sessions'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'), nullable=False)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=True)
    project_id = db.Column(db.String, db.ForeignKey('projects.id'), nullable=True)
    goal_text = db.Column(db.Text)
    phase = db.Column(db.String, default='gathering')  # gathering|drafting|refining|confirming|executed
    plan_json = db.Column(JSONB, default=dict)
    status = db.Column(db.String, default='active')  # active|executed|abandoned
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LlmCall(db.Model):
    """One row per raw LLM API call — the cost/observability ledger. Distinct from
    AgentToolCall (which logs *tool* invocations, a level above the model call itself):
    a single tool-using agent turn can involve one LLM call that decides to call a tool,
    then another LLM call to process the tool's result — both get logged here."""
    __tablename__ = 'llm_calls'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    session_id = db.Column(db.String, nullable=True)  # chat_sessions.id, MCP thread, or job id
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'), nullable=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=True)

    provider = db.Column(db.String, nullable=False, default='google')  # google|openai|anthropic
    model = db.Column(db.String, nullable=False)  # e.g. 'gemini-2.0-flash'
    node = db.Column(db.String, nullable=True)  # router|query_agent|crud_agent|analysis_agent|planning_agent|...

    prompt_tokens = db.Column(db.Integer, default=0)
    completion_tokens = db.Column(db.Integer, default=0)
    total_tokens = db.Column(db.Integer, default=0)
    estimated_cost_usd = db.Column(db.Float, default=0.0)

    latency_ms = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String, default='success')  # success|error
    error_message = db.Column(db.Text, nullable=True)

    call_metadata = db.Column('metadata', JSONB, default=dict)  # temperature, purpose, etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
