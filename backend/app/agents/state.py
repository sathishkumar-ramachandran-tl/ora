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


class SubTask(TypedDict):
    """One step in a recursive plan produced by graph_v2's planner_node."""
    id: int
    description: str
    status: str             # pending | done | failed
    result: Optional[str]


class ScratchpadState(TypedDict):
    """State for the Core Intelligence Layer (graph_v2) — a recursive plan/act/reflect
    loop with bounded replanning, replacing AgentState's single-hop router->one-agent
    dispatch. 'direct' requests skip straight to a single tool-using agent pass; 'agentic'
    requests are decomposed by planner_node and executed step-by-step with a reflection
    checkpoint after each step; 'plan' requests delegate to the existing multi-turn
    Planning Cortex (imported from orchestrator.py) as a named sub-agent.
    """
    messages: Annotated[list, add_messages]
    workspace_id: str
    user_id: str
    workspace_context: Optional[dict]

    # Set by classify_node; drives the top-level routing decision
    complexity: Optional[str]      # 'direct' | 'agentic' | 'plan'
    goal: Optional[str]

    # Recursive plan/act/reflect loop state
    plan: List[SubTask]
    working_memory: dict           # step_N -> result text, carried across replans
    current_step_index: int
    replan_count: int
    next_action: Optional[str]     # reflect_node's routing decision: continue|replan|done
    final_answer: Optional[str]

    # Reused verbatim by the delegated Planning Cortex sub-agent (multi-turn roadmap UX)
    planning_phase: Optional[str]
    draft_plan: Optional[dict]
    planning_project_id: Optional[str]
