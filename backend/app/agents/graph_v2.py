"""
Ora Core Intelligence Layer v2 — recursive plan/act/reflect orchestrator.

Architecture (the "Claude-Code-level" redesign, see the roadmap's Gap 5):

  User message
    └─► classify_node (Gemini Flash — cheap triage)
          ├─► direct_node     — single tool-using agent pass, for one-shot asks
          │                      ("list my tasks", "mark X done", "what's overdue")
          ├─► planner_node    — decomposes a multi-step goal into an ordered SubTask[]
          │     └─► executor_node ──► reflect_node ──┬─► executor_node (next step)
          │           ▲                              ├─► planner_node (bounded replan)
          │           └──────────────────────────────┘  └─► END (done, final_answer set)
          └─► planning_agent  — delegates to the existing multi-turn Planning Cortex
                                 (imported from orchestrator.py) for explicit, conversational
                                 project-roadmap building with a confirm-to-execute step.

Unlike the v1 orchestrator (router -> exactly one of four disjoint-tool agents, no
recursion), the 'agentic' path here is genuinely recursive: planner_node can be revisited
after a reflect_node verdict of 'replan', bounded by MAX_REPLANS, and every node binds to
the SAME unified tool registry (ALL_TOOLS — tasks, projects, calendar, modules), so a
single goal can span all three product modules without special-casing.

Feature-flagged via AGENT_ENGINE env var (default 'v2'); set AGENT_ENGINE=v1 to fall back
to the original orchestrator.py while this is being validated in production.
"""
import os
import json
import logging
from typing import Literal, Optional
from dotenv import load_dotenv

load_dotenv()

from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from .state import ScratchpadState
from .tools import ALL_TOOLS
from .checkpointer import get_checkpointer
from .llm_tracking import LlmUsageCallback
from .orchestrator import planning_node  # reused verbatim as the delegated Planning Cortex

logger = logging.getLogger(__name__)

FLASH_MODEL_NAME = "gemini-2.5-flash"
PRO_MODEL_NAME = "gemini-3.1-pro-preview"

MAX_PLAN_STEPS = 6
MAX_REPLANS = 2


def _usage_callback(state: ScratchpadState, config: RunnableConfig, node: str, model: str) -> dict:
    thread_id = ((config or {}).get("configurable") or {}).get("thread_id")
    callback = LlmUsageCallback(
        session_id=thread_id,
        workspace_id=state.get("workspace_id"),
        user_id=state.get("user_id"),
        node=node,
        model=model,
    )
    return {"callbacks": [callback]}


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return ''.join(
            part.get('text', '') if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content) if content else ''


def _flash_model(temperature=0.2):
    return ChatGoogleGenerativeAI(
        model=FLASH_MODEL_NAME,
        google_api_key=os.environ.get("GEMINI_API_KEY") or os.environ.get("API_KEY", ""),
        temperature=temperature,
        streaming=True,
    )


def _pro_model(temperature=0.3):
    return ChatGoogleGenerativeAI(
        model=PRO_MODEL_NAME,
        google_api_key=os.environ.get("GEMINI_API_KEY") or os.environ.get("API_KEY", ""),
        temperature=temperature,
        streaming=True,
    )


def _context_header(state: ScratchpadState) -> str:
    return (
        f"Workspace context: {json.dumps(state.get('workspace_context', {}))}\n"
        f"workspace_id for all operations: {state.get('workspace_id', '')}\n"
        f"user_id (current user): {state.get('user_id', '')}"
    )


# ---------------------------------------------------------------------------
# CLASSIFY NODE — cheap triage: direct vs agentic vs explicit planning
# ---------------------------------------------------------------------------

CLASSIFY_SYSTEM = """You are the Ora routing intelligence. Classify the user's request into exactly one word:

- direct   : a single lookup, single CRUD action, or a quick analysis answerable in one
             tool-using pass (e.g. "list my tasks", "mark X done", "what's overdue",
             "create a task called Y", "summarize my progress")
- agentic  : a multi-step goal that requires several ordered actions, possibly across
             different tools/modules, to fully accomplish (e.g. "set up my week: create
             the onboarding tasks and schedule focus blocks for them", "find a UPSC module,
             install it, and schedule its milestones", "plan my day around my meetings")
- plan     : the user explicitly wants a structured, multi-turn project roadmap built
             through back-and-forth conversation (e.g. "help me plan my new project",
             "let's plan the launch")

Reply with ONLY the lowercase word."""


def classify_node(state: ScratchpadState, config: RunnableConfig) -> dict:
    # Mid-conversation planning session in progress → keep routing to the Planning Cortex.
    if state.get("planning_phase") and state["planning_phase"] not in ("executed", None):
        return {"complexity": "plan"}

    messages = state["messages"]
    last_user_msg = next(
        (m.content for m in reversed(messages) if getattr(m, "type", "") == "human"), ""
    )

    try:
        llm = _flash_model()
        response = llm.invoke(
            [SystemMessage(content=CLASSIFY_SYSTEM), HumanMessage(content=last_user_msg)],
            config=_usage_callback(state, config, "classify", FLASH_MODEL_NAME),
        )
        complexity = _extract_text(response.content).strip().lower()
        if complexity not in ("direct", "agentic", "plan"):
            complexity = "direct"
    except Exception as e:
        logger.warning(f"classify_node error: {e}")
        complexity = "direct"

    return {"complexity": complexity, "goal": last_user_msg}


def _route_after_classify(state: ScratchpadState) -> Literal["direct", "agentic", "plan"]:
    complexity = state.get("complexity", "direct")
    return "agentic" if complexity == "agentic" else complexity


# ---------------------------------------------------------------------------
# DIRECT NODE — single agent pass, full tool registry
# ---------------------------------------------------------------------------

DIRECT_SYSTEM = """You are Ora's Intelligence Layer — one agent with full read/write
access to the user's workspace: tasks, projects, initiatives, calendar, and the module
marketplace. You reason about which tool(s) to call and act directly.

ADAPTIVE FORMAT — choose based on the request type, never default to prose:
- "how many / what is / who" → ONE precise answer, no preamble
- List of items → bullet list ONLY, no intro/outro paragraphs
- Status across multiple items → markdown table with | pipe format
- A create/update/delete action → confirm with ✓ (or ✗ on error), no paragraphs
- Deep analysis → ## headers + bullets, keep each section tight

RULES:
- NEVER start with "Sure!", "Great!", "Let me...", "I'll..." — go straight to the answer
- NEVER repeat the user's question back to them, never add filler closings
- Always use tool data — never guess IDs, names, dates, or counts
- Never invent workspace_id/project_id/event_id — look them up with a read tool first
- If the user asked you to do something, do it — don't ask permission first
- For bulk creates: use create_multiple_tasks (atomic), not N separate calls"""


def build_direct_agent():
    return create_react_agent(model=_pro_model(), tools=ALL_TOOLS, prompt=DIRECT_SYSTEM)


def direct_node(state: ScratchpadState, config: RunnableConfig) -> dict:
    agent = build_direct_agent()
    enriched_messages = [SystemMessage(content=_context_header(state))] + state["messages"]

    result = agent.invoke(
        {"messages": enriched_messages},
        config=_usage_callback(state, config, "direct_agent", PRO_MODEL_NAME),
    )
    return {"messages": result["messages"]}


# ---------------------------------------------------------------------------
# PLANNER NODE — decomposes a goal into an ordered SubTask[]
# ---------------------------------------------------------------------------

class PlanStepSpec(BaseModel):
    description: str = Field(description="A single concrete, tool-actionable step")


class SubTaskPlan(BaseModel):
    steps: list[PlanStepSpec]


PLANNER_SYSTEM = """You are the Ora planning cortex — decompose the user's goal into
an ordered list of concrete, tool-actionable steps for an execution agent to carry out
one at a time.

Rules:
- 2 to 6 steps. Merge trivial steps; split only where a genuinely distinct action/tool
  is needed.
- Each step must be executable given the outputs of prior steps — they run in strict
  order and later steps can rely on earlier results (e.g. an ID looked up in step 1).
- Do not include a final "summarize for the user" step — that happens automatically.
- Ground every step in what's actually possible: reading/creating/updating/deleting
  tasks, projects, or initiatives; creating/updating/deleting calendar events or finding
  availability; browsing, generating, or installing marketplace modules."""


def planner_node(state: ScratchpadState, config: RunnableConfig) -> dict:
    goal = state.get("goal") or next(
        (m.content for m in reversed(state["messages"]) if getattr(m, "type", "") == "human"), ""
    )

    replan_context = ""
    if state.get("plan"):
        replan_context = (
            f"\nThis is a REVISION of a previous plan. Progress/results so far: "
            f"{json.dumps(state.get('working_memory', {}))}\n"
            f"Produce a corrected plan that accounts for what's already been done."
        )

    model = _pro_model().with_structured_output(SubTaskPlan)
    prompt = (
        f"Goal: {goal}\n"
        f"Workspace context: {json.dumps(state.get('workspace_context', {}))}"
        f"{replan_context}"
    )

    try:
        result: SubTaskPlan = model.invoke(
            [SystemMessage(content=PLANNER_SYSTEM), HumanMessage(content=prompt)],
            config=_usage_callback(state, config, "planner", PRO_MODEL_NAME),
        )
        steps = result.steps[:MAX_PLAN_STEPS] or [PlanStepSpec(description=goal)]
    except Exception as e:
        logger.warning(f"planner_node error: {e}")
        steps = [PlanStepSpec(description=goal)]

    plan = [
        {"id": i, "description": s.description, "status": "pending", "result": None}
        for i, s in enumerate(steps)
    ]
    return {
        "goal": goal,
        "plan": plan,
        "current_step_index": 0,
        "working_memory": state.get("working_memory", {}),
    }


# ---------------------------------------------------------------------------
# EXECUTOR NODE — runs one plan step with the full tool registry
# ---------------------------------------------------------------------------

EXECUTOR_SYSTEM = """You are Ora's execution agent, carrying out one step of a larger
plan. Use tools to accomplish exactly the step you're given — nothing more, nothing less.
Never invent IDs; look them up with a read tool if you don't already have them from prior
steps. When finished, reply with a one or two sentence summary of what you did or found —
this summary is handed to the next step, so include any IDs or facts it might need."""


def build_executor_agent():
    return create_react_agent(model=_flash_model(), tools=ALL_TOOLS, prompt=EXECUTOR_SYSTEM)


def executor_node(state: ScratchpadState, config: RunnableConfig) -> dict:
    plan = state["plan"]
    idx = state["current_step_index"]
    step = plan[idx]
    working_memory = state.get("working_memory", {})

    agent = build_executor_agent()
    step_instruction = (
        f"Overall goal: {state.get('goal', '')}\n"
        f"Progress so far: {json.dumps(working_memory) if working_memory else 'none yet'}\n"
        f"Your task right now (step {idx + 1}/{len(plan)}): {step['description']}"
    )
    step_messages = [
        SystemMessage(content=_context_header(state)),
        HumanMessage(content=step_instruction),
    ]

    try:
        result = agent.invoke(
            {"messages": step_messages},
            config=_usage_callback(state, config, "executor", FLASH_MODEL_NAME),
        )
        step_result_text = _extract_text(result["messages"][-1].content) if result["messages"] else ""
        new_messages = result["messages"]
        status = "done"
    except Exception as e:
        logger.exception("executor_node failed on step %s", idx)
        step_result_text = f"Step failed: {e}"
        new_messages = [AIMessage(content=f"⚠️ Step {idx + 1} failed: {e}")]
        status = "failed"

    new_plan = [dict(s) for s in plan]
    new_plan[idx] = {**step, "status": status, "result": step_result_text}

    return {
        "messages": new_messages,
        "plan": new_plan,
        "working_memory": {**working_memory, f"step_{idx + 1}": step_result_text},
    }


# ---------------------------------------------------------------------------
# REFLECT NODE — checkpoint after each step: continue | replan | done
# ---------------------------------------------------------------------------

class ReflectDecision(BaseModel):
    action: str = Field(description="continue | replan | done")
    final_answer: str = Field(default="", description="Set only when action='done' — a user-facing summary of the outcome")
    replan_reason: str = Field(default="", description="Set only when action='replan'")


REFLECT_SYSTEM = """You are the reflection checkpoint in an autonomous agent loop. After
each executed step, decide exactly one of:
- continue : more steps remain and nothing needs to change — proceed to the next step
- replan   : the plan is wrong, incomplete, or the step failed in a way that invalidates
             the remaining steps — give a concrete replan_reason
- done     : the goal is fully satisfied (all steps succeeded, or enough is done to
             answer the user even if steps remain) — give a final_answer that reports
             the concrete outcome to the user (IDs, counts, what was created/found),
             formatted the way Ora normally replies: no filler, ✓ for confirmations.

Be decisive. Prefer continue/done over replan unless something concrete is broken."""


def reflect_node(state: ScratchpadState, config: RunnableConfig) -> dict:
    plan = state["plan"]
    idx = state["current_step_index"]
    step = plan[idx]
    steps_remaining = len(plan) - idx - 1

    model = _flash_model().with_structured_output(ReflectDecision)
    prompt = (
        f"Goal: {state.get('goal', '')}\n"
        f"Full plan: {json.dumps([s['description'] for s in plan])}\n"
        f"Just completed step {idx + 1}/{len(plan)}: {step['description']}\n"
        f"Step status: {step['status']}\n"
        f"Step result: {step.get('result', '')}\n"
        f"Steps remaining after this one: {steps_remaining}"
    )

    try:
        result: ReflectDecision = model.invoke(
            [SystemMessage(content=REFLECT_SYSTEM), HumanMessage(content=prompt)],
            config=_usage_callback(state, config, "reflect", FLASH_MODEL_NAME),
        )
        action = result.action if result.action in ("continue", "replan", "done") else "continue"
        final_answer = result.final_answer
    except Exception as e:
        logger.warning(f"reflect_node error: {e}")
        action = "continue"
        final_answer = ""

    if steps_remaining <= 0 and action == "continue":
        action = "done"  # no more steps to continue to — force completion

    updates: dict = {"next_action": action}

    if action == "done":
        summary = final_answer or step.get("result") or "Done."
        updates["final_answer"] = summary
        updates["messages"] = [AIMessage(content=summary)]
    elif action == "continue":
        updates["current_step_index"] = idx + 1
    elif action == "replan":
        updates["replan_count"] = state.get("replan_count", 0) + 1

    return updates


def _route_after_reflect(state: ScratchpadState) -> Literal["executor", "planner", "end"]:
    action = state.get("next_action", "done")
    if action == "done":
        return "end"
    if action == "replan":
        if state.get("replan_count", 0) > MAX_REPLANS:
            return "end"  # bail out rather than loop forever; last step's result stands as the answer
        return "planner"
    return "executor"


# ---------------------------------------------------------------------------
# GRAPH ASSEMBLY
# ---------------------------------------------------------------------------

_compiled_graph = None


def create_orchestrator():
    """Return the compiled Core Intelligence Layer graph (singleton per process)."""
    global _compiled_graph
    if _compiled_graph is not None:
        return _compiled_graph

    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        checkpointer = get_checkpointer(database_url)
    else:
        logger.warning("DATABASE_URL not set — falling back to in-memory checkpointer (state will not persist)")
        checkpointer = MemorySaver()

    graph = StateGraph(ScratchpadState)

    graph.add_node("classify", classify_node)
    graph.add_node("direct", direct_node)
    graph.add_node("planner", planner_node)
    graph.add_node("executor", executor_node)
    graph.add_node("reflect", reflect_node)
    graph.add_node("planning_agent", planning_node)

    graph.set_entry_point("classify")

    graph.add_conditional_edges(
        "classify",
        _route_after_classify,
        {"direct": "direct", "agentic": "planner", "plan": "planning_agent"},
    )

    graph.add_edge("direct", END)
    graph.add_edge("planning_agent", END)
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", "reflect")

    graph.add_conditional_edges(
        "reflect",
        _route_after_reflect,
        {"executor": "executor", "planner": "planner", "end": END},
    )

    _compiled_graph = graph.compile(checkpointer=checkpointer)
    return _compiled_graph
