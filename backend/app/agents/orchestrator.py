"""
Sindhai Multi-Agent Orchestrator (LangGraph)

Architecture:
  User message
    └─► router_node (Gemini Flash — classify intent)
          ├─► query_agent   (Gemini 2.5 Pro — read + analyze)
          ├─► crud_agent    (Gemini 2.5 Flash — mutations)
          ├─► planning_agent (Gemini 2.5 Pro — multi-turn planning)
          └─► analysis_agent (Gemini 2.5 Pro — deep insights)

State persists across HTTP calls via LangGraph MemorySaver (thread_id = session_id).
"""
import os
import json
import logging
from typing import Literal
from dotenv import load_dotenv

load_dotenv()  # ensure .env is loaded when orchestrator is imported standalone

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from .state import AgentState, PlanState
from .tools import READ_TOOLS, CRUD_TOOLS, PLANNING_TOOLS, ALL_TOOLS

logger = logging.getLogger(__name__)


def _extract_text(content) -> str:
    """Normalize Gemini content which may be a str or a list of content parts."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return ''.join(
            part.get('text', '') if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content) if content else ''


# ---------------------------------------------------------------------------
# Model factory — lazy init to avoid loading at import time
# ---------------------------------------------------------------------------

def _flash_model():
    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=os.environ.get("API_KEY", ""),
        temperature=0.2,
        streaming=True
    )

def _pro_model():
    return ChatGoogleGenerativeAI(
        model="gemini-3.1-pro-preview",
        google_api_key=os.environ.get("API_KEY", ""),
        temperature=0.3,
        streaming=True
    )


# ---------------------------------------------------------------------------
# SYSTEM PROMPTS
# ---------------------------------------------------------------------------

ROUTER_SYSTEM = """You are the Sindhai routing intelligence. Classify the user's intent into exactly one of:
- crud     : user wants to CREATE, UPDATE, DELETE tasks/projects/initiatives
- query    : user wants to READ, LIST, SEARCH, or GET information
- plan     : user wants to PLAN a new project with AI assistance (multi-turn)
- analyze  : user wants deep ANALYSIS, INSIGHTS, SUGGESTIONS, or PRIORITIZATION

Reply with ONLY the lowercase intent word. Nothing else."""


QUERY_SYSTEM = """You are Sindhai's Intelligence Layer — the user's personal data expert.

ADAPTIVE FORMAT — choose based on the request type, never default to prose:
- "how many / what is / who" → ONE precise answer, no preamble
- List of items → bullet list ONLY, no intro/outro paragraphs
- Status across multiple items → markdown table with | pipe format
- Quick summary → 3-5 bullet points, most important first
- Detailed breakdown → ## headers + bullets, keep each section tight

RULES:
- NEVER start with "Sure!", "Great!", "Let me...", "I'll..." — go straight to the answer
- NEVER repeat the user's question back to them
- NEVER add filler closings ("Hope this helps!", "Feel free to ask!")
- Always use tool data — never guess IDs, names, or counts
- When listing tasks: title • status • priority — nothing else unless asked
- Numbers are exact (not "around 3" when you have the data)"""


CRUD_SYSTEM = """You are Sindhai's Execution Engine — you act, you don't deliberate.

CONFIRMATION FORMAT after every operation:
✓ Created "Task title" (priority) → Project Name
✓ Moved "Task title" → new-status
✓ Deleted "Task title" — permanently removed

RULES:
- Use ✓ for success, ✗ for errors — no paragraphs
- For bulk creates: "Created X tasks in [Project]:" then one bullet per task title
- For deletes: always warn "this cannot be undone"
- NEVER ask permission — user said it, do it
- Use create_multiple_tasks for 2+ tasks — it's atomic
- Never invent project_ids — use get_projects to look up first
- Always report IDs of created resources"""


ANALYSIS_SYSTEM = """You are Sindhai's Strategic Cortex — a Chief of Staff who thinks in systems.

MANDATORY STRUCTURE — always use exactly this format:

## TL;DR
[One sentence: the single most important thing the user needs to know right now]

## Workspace Health
| Metric | Value | Signal |
|--------|-------|--------|
| Total tasks | X | 🟢/🟡/🔴 |
| Completion rate | X% | 🟢/🟡/🔴 |
| In progress | X | 🟢/🟡/🔴 |
| Blocked/stalled | X | 🟢/🟡/🔴 |

## Top Bottlenecks
- **[Specific bottleneck]** — [why it matters, backed by data]
- **[Specific bottleneck]** — [why it matters]

## Priority Actions This Week
1. **[Specific action]** — why: [measurable reason]
2. **[Specific action]** — why: [measurable reason]
3. **[Specific action]** — why: [measurable reason]

## Risk Flags
- [Risk] → [consequence if ignored]

RULES:
- Be a truth-teller — if something is broken, say it plainly
- Every claim must trace to tool data (use analyze_workspace_progress + get_workspace_summary)
- Max 3 items per section — ruthless prioritization
- Health signals: 🟢 on track · 🟡 watch it · 🔴 critical"""


PLANNING_SYSTEM = """You are Sindhai's Planning Cortex — you build execution-ready roadmaps, not wish lists.
You are the user's strategic thought partner. Think like a Chief of Staff.

━━━ PHASE 1: GATHER ━━━
Always start by calling get_workspace_summary to understand existing context.
Then ask MAX 2 targeted questions — only what you cannot infer:
  1. What is the target deadline or launch date?
  2. Any hard constraints (team size, budget, dependencies)?
Do NOT ask what the project is. Do NOT ask generic open-ended questions.

━━━ PHASE 2: DEEP ROADMAP ━━━
Generate a milestone-based execution plan. Use EXACTLY this format:

## 🗺️ Roadmap: [Project Name]
**Goal:** [what "done" looks like — one crisp sentence]
**Timeline:** [duration] · **Total effort:** ~[X]h

---
### 📍 Milestone 1: [Name] — *Target: [Week/Date]*
> [What this milestone unlocks or proves]

| Task | Priority | Est. |
|------|----------|------|
| [Task title] | 🔴 critical | Xh |
| [Task title] | 🟠 high | Xh |
| [Task title] | 🟡 medium | Xh |
| [Buffer & review] | 🟡 medium | Xh |

---
### 📍 Milestone 2: [Name] — *Target: [Week/Date]*
[same structure]

---
**Total:** [N] tasks · [M] milestones · ~[X]h estimated effort

Reply **"confirm"** to create all tasks now, or tell me what to adjust.

━━━ PHASE 3: REFINE ━━━
Make targeted corrections only — don't regenerate the whole plan.
Acknowledge changes: "Updated: moved X to M2, increased Y estimate to 8h"

━━━ PHASE 4: EXECUTE ━━━
When user confirms → call create_project_plan with the full structured plan.
On success → report: "✓ Created [N] tasks across [M] milestones in [Project]. Board updated."

QUALITY STANDARDS:
- 3-5 milestones (not more, not fewer) for substantial projects
- 4-7 tasks per milestone — not an exhaustive dump
- Estimates: honest and padded 15% for unknowns
- Every milestone must include a review/QA task
- Tasks must align with the project mission from workspace context"""


# ---------------------------------------------------------------------------
# ROUTER NODE
# ---------------------------------------------------------------------------

def router_node(state: AgentState) -> dict:
    """Classify intent using a fast LLM call. Updates state.intent."""
    messages = state["messages"]
    last_user_msg = next(
        (m.content for m in reversed(messages) if hasattr(m, "type") and m.type == "human"),
        ""
    )

    # Planning in-progress → keep routing to planning agent
    if state.get("planning_phase") and state["planning_phase"] not in ("executed", None):
        return {"intent": "plan", "active_agent": "planning"}

    try:
        llm = _flash_model()
        response = llm.invoke([
            SystemMessage(content=ROUTER_SYSTEM),
            HumanMessage(content=last_user_msg)
        ])
        intent = _extract_text(response.content).strip().lower()
        if intent not in ("crud", "query", "plan", "analyze"):
            intent = "query"  # default
    except Exception as e:
        logger.warning(f"Router error: {e}")
        intent = "query"

    return {"intent": intent, "active_agent": intent}


def route_decision(state: AgentState) -> Literal["query", "crud", "plan", "analyze"]:
    return state.get("intent", "query")


# ---------------------------------------------------------------------------
# QUERY AGENT NODE
# ---------------------------------------------------------------------------

def build_query_agent():
    llm = _pro_model()
    return create_react_agent(
        model=llm,
        tools=READ_TOOLS,
        prompt=QUERY_SYSTEM
    )

def query_node(state: AgentState) -> dict:
    agent = build_query_agent()
    workspace_ctx = state.get("workspace_context", {})
    # Inject workspace context as the first system message
    enriched_messages = [
        SystemMessage(content=f"Workspace context: {json.dumps(workspace_ctx)}")
    ] + state["messages"]

    result = agent.invoke({"messages": enriched_messages})
    return {"messages": result["messages"]}


# ---------------------------------------------------------------------------
# CRUD AGENT NODE
# ---------------------------------------------------------------------------

def build_crud_agent():
    llm = _flash_model()
    return create_react_agent(
        model=llm,
        tools=CRUD_TOOLS,
        prompt=CRUD_SYSTEM
    )

def crud_node(state: AgentState) -> dict:
    agent = build_crud_agent()
    workspace_ctx = state.get("workspace_context", {})
    enriched_messages = [
        SystemMessage(content=(
            f"Workspace context: {json.dumps(workspace_ctx)}\n"
            f"workspace_id for all operations: {state.get('workspace_id', '')}"
        ))
    ] + state["messages"]

    result = agent.invoke({"messages": enriched_messages})
    return {"messages": result["messages"]}


# ---------------------------------------------------------------------------
# ANALYSIS AGENT NODE
# ---------------------------------------------------------------------------

def build_analysis_agent():
    llm = _pro_model()
    return create_react_agent(
        model=llm,
        tools=READ_TOOLS,
        prompt=ANALYSIS_SYSTEM
    )

def analysis_node(state: AgentState) -> dict:
    agent = build_analysis_agent()
    workspace_ctx = state.get("workspace_context", {})
    enriched_messages = [
        SystemMessage(content=f"Workspace context: {json.dumps(workspace_ctx)}")
    ] + state["messages"]

    result = agent.invoke({"messages": enriched_messages})
    return {"messages": result["messages"]}


# ---------------------------------------------------------------------------
# PLANNING AGENT NODE (Multi-turn via checkpointing)
# ---------------------------------------------------------------------------

def build_planning_agent():
    llm = _pro_model()
    return create_react_agent(
        model=llm,
        tools=PLANNING_TOOLS,
        prompt=PLANNING_SYSTEM
    )

def planning_node(state: AgentState) -> dict:
    agent = build_planning_agent()
    workspace_ctx = state.get("workspace_context", {})
    phase = state.get("planning_phase", "gathering")
    project_id = state.get("planning_project_id", "")
    draft = state.get("draft_plan", {})

    enriched_messages = [
        SystemMessage(content=(
            f"CURRENT CONTEXT:\n"
            f"- Planning phase: {phase}\n"
            f"- Target project_id: {project_id or 'TBD — may need to create or select one'}\n"
            f"- Draft plan so far: {json.dumps(draft) if draft else 'none yet'}\n"
            f"- Workspace snapshot: {json.dumps(workspace_ctx)}"
        ))
    ] + state["messages"]

    result = agent.invoke({"messages": enriched_messages})

    # Advance phase based on conversation signals
    new_phase = phase
    last_ai = _extract_text(result["messages"][-1].content) if result["messages"] else ""
    last_ai_lower = last_ai.lower()

    # Detect if create_project_plan was called (plan was executed)
    tool_names_called = [
        m.name for m in result["messages"]
        if getattr(m, "type", "") == "tool"
    ]
    plan_executed = "create_project_plan" in tool_names_called or "create_multiple_tasks" in tool_names_called

    if plan_executed:
        new_phase = "executed"
    elif phase == "gathering":
        # Move to drafting when the AI presents a roadmap
        if "milestone" in last_ai_lower or "roadmap" in last_ai_lower or "## 🗺️" in last_ai:
            new_phase = "drafting"
    elif phase == "drafting":
        # Move to refining after the roadmap is shown; user may request changes
        if any(w in last_ai_lower for w in ("confirm", "adjust", "reply")):
            new_phase = "refining"
    elif phase == "refining":
        if any(w in last_ai_lower for w in ("confirm", "create all", "ready to execute")):
            new_phase = "confirming"

    return {
        "messages": result["messages"],
        "planning_phase": new_phase
    }


# ---------------------------------------------------------------------------
# GRAPH ASSEMBLY
# ---------------------------------------------------------------------------

_checkpointer = MemorySaver()
_compiled_graph = None

def create_orchestrator():
    """Return the compiled LangGraph orchestrator (singleton per process)."""
    global _compiled_graph
    if _compiled_graph is not None:
        return _compiled_graph

    graph = StateGraph(AgentState)

    graph.add_node("router", router_node)
    graph.add_node("query_agent", query_node)
    graph.add_node("crud_agent", crud_node)
    graph.add_node("analysis_agent", analysis_node)
    graph.add_node("planning_agent", planning_node)

    graph.set_entry_point("router")

    graph.add_conditional_edges(
        "router",
        route_decision,
        {
            "query": "query_agent",
            "crud": "crud_agent",
            "analyze": "analysis_agent",
            "plan": "planning_agent"
        }
    )

    graph.add_edge("query_agent", END)
    graph.add_edge("crud_agent", END)
    graph.add_edge("analysis_agent", END)
    graph.add_edge("planning_agent", END)

    _compiled_graph = graph.compile(checkpointer=_checkpointer)
    return _compiled_graph
