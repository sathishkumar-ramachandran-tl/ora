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
    run_id = db.Column(db.String, db.ForeignKey('agent_runs.id'), nullable=True)
    action_id = db.Column(db.String, db.ForeignKey('agent_actions.id'), nullable=True)
    execution_status = db.Column(db.String, default='SUCCEEDED')  # PENDING|RUNNING|SUCCEEDED|FAILED|UNKNOWN
    verification_status = db.Column(db.String, default='NOT_REQUIRED')  # NOT_REQUIRED|UNVERIFIED|VERIFIED|FAILED|RECONCILING
    attempt_number = db.Column(db.Integer, default=1)
    error_class = db.Column(db.String, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    external_provider = db.Column(db.String, nullable=True)
    external_resource_id = db.Column(db.String, nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    verified_at = db.Column(db.DateTime, nullable=True)


class AgentRun(db.Model):
    """One durable record per user request handled by the agentic control plane."""
    __tablename__ = 'agent_runs'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    request_id = db.Column(db.String, nullable=True)
    session_id = db.Column(db.String, nullable=True)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'), nullable=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=True)
    status = db.Column(db.String, default='CREATED')
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    error_class = db.Column(db.String, nullable=True)
    error_message = db.Column(db.Text, nullable=True)


class AgentAction(db.Model):
    """User-visible operation proposed or executed by an agent run."""
    __tablename__ = 'agent_actions'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    run_id = db.Column(db.String, db.ForeignKey('agent_runs.id'), nullable=False)
    parent_action_id = db.Column(db.String, db.ForeignKey('agent_actions.id'), nullable=True)
    action_type = db.Column(db.String, nullable=False)
    resource_type = db.Column(db.String, nullable=True)
    resource_id = db.Column(db.String, nullable=True)
    status = db.Column(db.String, default='PROPOSED')
    risk_level = db.Column(db.String, default='MEDIUM')
    confirmation_required = db.Column(db.Boolean, default=False)
    idempotency_key = db.Column(db.String, nullable=True, index=True)
    request_fingerprint = db.Column(db.String, nullable=True, index=True)
    proposed_args = db.Column(JSONB, default=dict)
    before_state = db.Column(JSONB, default=dict)
    after_state = db.Column(JSONB, default=dict)
    reversible = db.Column(db.Boolean, default=False)
    compensation_action_type = db.Column(db.String, nullable=True)
    original_action_id = db.Column(db.String, db.ForeignKey('agent_actions.id'), nullable=True)
    undo_action_id = db.Column(db.String, db.ForeignKey('agent_actions.id'), nullable=True)
    undo_status = db.Column(db.String, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)


class PlanProposal(db.Model):
    """Structured AI plan proposal. Not domain state until compiled and applied."""
    __tablename__ = 'plan_proposals'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    run_id = db.Column(db.String, db.ForeignKey('agent_runs.id'), nullable=True)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'), nullable=False)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=True)
    scope_level = db.Column(db.String, default='workspace')
    scope_project_id = db.Column(db.String, db.ForeignKey('projects.id'), nullable=True)
    scope_task_id = db.Column(db.String, db.ForeignKey('tasks.id'), nullable=True)
    title = db.Column(db.String, nullable=False)
    goal = db.Column(db.Text)
    status = db.Column(db.String, default='DRAFT')
    version = db.Column(db.Integer, default=1)
    quality_status = db.Column(db.String, default='UNREVIEWED')
    supersedes_id = db.Column(db.String, db.ForeignKey('plan_proposals.id'), nullable=True)
    revision_reason = db.Column(db.Text, nullable=True)
    content = db.Column(JSONB, default=dict)
    planning_context = db.Column(JSONB, default=dict)
    quality_report = db.Column(JSONB, default=dict)
    duplication_report = db.Column(JSONB, default=dict)
    compiled_actions = db.Column(JSONB, default=list)
    application_result = db.Column(JSONB, default=dict)
    applied_action_id = db.Column(db.String, db.ForeignKey('agent_actions.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    applied_at = db.Column(db.DateTime, nullable=True)


class Concept(db.Model):
    """Stable concept identity inside a workspace/domain."""
    __tablename__ = 'concepts'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'), nullable=False)
    concept_key = db.Column(db.String, nullable=False)
    canonical_name = db.Column(db.String, nullable=False)
    domain = db.Column(db.String, nullable=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (
        db.UniqueConstraint('workspace_id', 'concept_key', name='uq_concepts_workspace_key'),
    )


class ConceptAlias(db.Model):
    __tablename__ = 'concept_aliases'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    concept_id = db.Column(db.String, db.ForeignKey('concepts.id'), nullable=False)
    alias = db.Column(db.String, nullable=False)
    normalized_alias = db.Column(db.String, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (
        db.UniqueConstraint('concept_id', 'normalized_alias', name='uq_concept_alias_normalized'),
    )


class ConceptRelationship(db.Model):
    __tablename__ = 'concept_relationships'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'), nullable=False)
    source_concept_id = db.Column(db.String, db.ForeignKey('concepts.id'), nullable=False)
    target_concept_id = db.Column(db.String, db.ForeignKey('concepts.id'), nullable=False)
    relationship_type = db.Column(db.String, nullable=False)  # REQUIRES|BUILDS_ON|RELATED_TO
    evidence = db.Column(JSONB, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (
        db.UniqueConstraint(
            'source_concept_id', 'target_concept_id', 'relationship_type',
            name='uq_concept_relationship',
        ),
    )


class CoverageRecord(db.Model):
    """What a plan/project covers. Completion here is not mastery."""
    __tablename__ = 'coverage_records'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'), nullable=False)
    project_id = db.Column(db.String, db.ForeignKey('projects.id'), nullable=True)
    plan_proposal_id = db.Column(db.String, db.ForeignKey('plan_proposals.id'), nullable=True)
    concept_id = db.Column(db.String, db.ForeignKey('concepts.id'), nullable=False)
    concept_key = db.Column(db.String, nullable=False)
    concept_name = db.Column(db.String, nullable=False)
    domain = db.Column(db.String, nullable=True)
    coverage_type = db.Column(db.String, nullable=False)  # INTRODUCES|PRACTICES|DEEPENS|ASSESSES|REVIEWS
    depth = db.Column(db.String, nullable=False)  # FOUNDATIONAL|INTERMEDIATE|ADVANCED
    status = db.Column(db.String, default='PLANNED')  # PLANNED|IN_PROGRESS|COMPLETED|NEEDS_REVIEW
    source_type = db.Column(db.String, nullable=False)  # plan|milestone|task|manual
    source_id = db.Column(db.String, nullable=True)
    evidence = db.Column(JSONB, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (
        db.UniqueConstraint(
            'workspace_id', 'plan_proposal_id', 'concept_key', 'coverage_type', 'depth', 'source_type', 'source_id',
            name='uq_coverage_record_identity',
        ),
    )


class ResearchEvidence(db.Model):
    """Normalized source evidence used by planning/evaluation."""
    __tablename__ = 'research_evidence'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'), nullable=False)
    run_id = db.Column(db.String, db.ForeignKey('agent_runs.id'), nullable=True)
    domain = db.Column(db.String, nullable=False)
    topic = db.Column(db.String, nullable=True)
    source_type = db.Column(db.String, nullable=False)
    title = db.Column(db.String, nullable=False)
    source_url = db.Column(db.String, nullable=True)
    authority_level = db.Column(db.String, nullable=False)
    claims = db.Column(JSONB, default=list)
    topics = db.Column(JSONB, default=list)
    relevance = db.Column(db.String, nullable=True)
    content_hash = db.Column(db.String, nullable=True)
    retrieved_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CompetencyEvidence(db.Model):
    """Evidence that may update mastery/capability state. Task completion alone is not evidence."""
    __tablename__ = 'competency_evidence'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'), nullable=False)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=True)
    concept_id = db.Column(db.String, db.ForeignKey('concepts.id'), nullable=True)
    evidence_type = db.Column(db.String, nullable=False)  # self_report|assessment|project_artifact|manual_confirmation
    evidence_ref = db.Column(db.String, nullable=True)
    result = db.Column(JSONB, default=dict)
    strength = db.Column(db.String, default='WEAK')  # WEAK|MODERATE|STRONG
    assessed_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MasteryRecord(db.Model):
    """Learning-specific view of competency. Status is ordinal, evidence-backed."""
    __tablename__ = 'mastery_records'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'), nullable=False)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=True)
    concept_id = db.Column(db.String, db.ForeignKey('concepts.id'), nullable=False)
    concept_key = db.Column(db.String, nullable=False)
    status = db.Column(db.String, default='UNKNOWN')  # UNKNOWN|INTRODUCED|PRACTICED|PROFICIENT|STRONG|NEEDS_REVIEW
    evidence_type = db.Column(db.String, nullable=True)
    evidence_id = db.Column(db.String, db.ForeignKey('competency_evidence.id'), nullable=True)
    assessed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (
        db.UniqueConstraint('workspace_id', 'user_id', 'concept_id', name='uq_mastery_user_concept'),
    )


class PlanRevisionProposal(db.Model):
    """Differential revision proposal for an existing plan."""
    __tablename__ = 'plan_revision_proposals'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'), nullable=False)
    base_plan_id = db.Column(db.String, db.ForeignKey('plan_proposals.id'), nullable=False)
    base_version = db.Column(db.Integer, nullable=False)
    trigger = db.Column(db.String, nullable=False)
    hard_constraints = db.Column(JSONB, default=list)
    soft_preferences = db.Column(JSONB, default=list)
    operations = db.Column(JSONB, default=list)
    rationale = db.Column(db.Text, nullable=True)
    status = db.Column(db.String, default='PROPOSED')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    applied_plan_id = db.Column(db.String, db.ForeignKey('plan_proposals.id'), nullable=True)


class ScheduleProposal(db.Model):
    """Proposal-first scheduling plan. It is not committed calendar state until applied."""
    __tablename__ = 'schedule_proposals'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    run_id = db.Column(db.String, db.ForeignKey('agent_runs.id'), nullable=True)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'), nullable=False)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=True)
    status = db.Column(db.String, default='DRAFT')  # DRAFT|READY|INFEASIBLE|APPLYING|APPLIED|PARTIALLY_APPLIED|FAILED
    version = db.Column(db.Integer, default=1)
    window_start = db.Column(db.DateTime, nullable=False)
    window_end = db.Column(db.DateTime, nullable=False)
    timezone = db.Column(db.String, default='UTC')
    constraints = db.Column(JSONB, default=list)
    sessions = db.Column(JSONB, default=list)
    summary = db.Column(JSONB, default=dict)
    compiled_actions = db.Column(JSONB, default=list)
    application_result = db.Column(JSONB, default=dict)
    applied_action_id = db.Column(db.String, db.ForeignKey('agent_actions.id'), nullable=True)
    supersedes_id = db.Column(db.String, db.ForeignKey('schedule_proposals.id'), nullable=True)
    revision_reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    applied_at = db.Column(db.DateTime, nullable=True)


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
