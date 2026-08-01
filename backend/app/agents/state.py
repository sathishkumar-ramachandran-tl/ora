from typing import TypedDict, Annotated, Optional, List
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Shared state flowing through the multi-agent graph."""
    messages: Annotated[list, add_messages]
    workspace_id: str
    user_id: str
    # Classified by router node; drives conditional routing
    intent: Optional[str]          # 'crud' | 'query' | 'plan' | 'analyze'
    active_agent: Optional[str]
    # Workspace snapshot injected at session start for grounding
    workspace_context: Optional[dict]
    # Multi-turn planning state (persisted via LangGraph checkpoints)
    planning_phase: Optional[str]  # 'gathering' | 'drafting' | 'refining' | 'confirming' | 'executed'
    draft_plan: Optional[dict]     # {project_id, tasks: [...], questions: [...]}
    planning_project_id: Optional[str]


class PlanState(TypedDict):
    """State for the Planning sub-graph (multi-turn)."""
    messages: Annotated[list, add_messages]
    workspace_id: str
    user_id: str
    project_id: Optional[str]
    workspace_context: Optional[dict]
    phase: str                     # gathering → drafting → refining → confirming → executed
    draft_tasks: List[dict]
    clarification_history: List[dict]  # [{question, answer}]
    corrections: List[str]
    confirmed: bool
