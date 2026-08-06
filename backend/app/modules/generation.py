"""
Module generation graph (Phase 1 — Agentic Module Generation).

outline_node -> expand_node -> critique_node -> {expand_node (revise) | materialize_node | END}

Runs as a Core-Intelligence-style bounded plan/act/reflect loop, invoked from a Flask
background thread (see routes.py's generate_module_async) so a multi-minute generation
doesn't block the request. Each stage persists to ModuleTemplateVersion so a crash mid-
generation leaves an inspectable partial result rather than silently losing work.
"""
import os
import json
import logging
from typing import TypedDict, Optional

from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)

MAX_CRITIQUE_ROUNDS = 2

PRO_MODEL_NAME = "gemini-3.1-pro-preview"
FLASH_MODEL_NAME = "gemini-2.5-flash"


def _pro_model(temperature=0.3):
    return ChatGoogleGenerativeAI(
        model=PRO_MODEL_NAME,
        google_api_key=os.environ.get("GEMINI_API_KEY") or os.environ.get("API_KEY", ""),
        temperature=temperature,
    )


def _flash_model(temperature=0.2):
    return ChatGoogleGenerativeAI(
        model=FLASH_MODEL_NAME,
        google_api_key=os.environ.get("GEMINI_API_KEY") or os.environ.get("API_KEY", ""),
        temperature=temperature,
    )


# ---------------------------------------------------------------------------
# Structured output schemas
# ---------------------------------------------------------------------------

class TaskSpec(BaseModel):
    title: str
    description: str = ""
    priority: str = Field(default="medium", description="low|medium|high|critical")
    estimated_hours: float = 2.0


class MilestoneSpec(BaseModel):
    title: str
    description: str = ""
    order: int = 0
    tasks: list[TaskSpec] = Field(default_factory=list)


class OutlineResult(BaseModel):
    milestones: list[MilestoneSpec]


class MilestoneTasksResult(BaseModel):
    tasks: list[TaskSpec]


class CritiqueResult(BaseModel):
    approve: bool
    feedback: str = ""


# ---------------------------------------------------------------------------
# Graph state
# ---------------------------------------------------------------------------

class GenerationState(TypedDict):
    goal: str
    category: str
    difficulty: str
    module_template_version_id: str
    milestones: list[dict]
    critique_round: int
    approved: bool
    feedback: Optional[str]
    error: Optional[str]


def _persist_progress(state: GenerationState, status: str, error: str = None):
    """Write current milestones/status to the version row — makes a partial/interrupted
    generation inspectable rather than silently losing work if the process restarts."""
    from ..core.extensions import db
    from .models import ModuleTemplateVersion

    version = db.session.get(ModuleTemplateVersion, state["module_template_version_id"])
    if not version:
        return
    version.structure_json = {"milestones": state["milestones"]}
    version.generation_status = status
    version.generation_error = error
    db.session.commit()


def outline_node(state: GenerationState) -> dict:
    model = _pro_model().with_structured_output(OutlineResult)
    prompt = (
        f"Design a learning/execution module for this goal: \"{state['goal']}\"\n"
        f"Category: {state['category']}. Difficulty: {state['difficulty']}.\n\n"
        "Produce a phase-by-phase milestone skeleton (4-8 milestones, ordered) that fully "
        "covers the goal. For each milestone give a clear title, a one-sentence description, "
        "and leave `tasks` empty — task-level detail is generated in a later step."
    )
    try:
        result: OutlineResult = model.invoke([
            SystemMessage(content="You are Ora's module-design agent. Be concrete and scoped, not generic."),
            HumanMessage(content=prompt),
        ])
        milestones = [m.model_dump() for m in result.milestones]
        for i, m in enumerate(milestones):
            m["order"] = i
        state = {**state, "milestones": milestones}
        _persist_progress(state, status="generating")
        return state
    except Exception as e:
        logger.exception("outline_node failed")
        return {**state, "error": str(e)}


def expand_node(state: GenerationState) -> dict:
    if state.get("error"):
        return state
    model = _pro_model().with_structured_output(MilestoneTasksResult)
    milestones = state["milestones"]

    for milestone in milestones:
        if milestone.get("tasks"):
            continue  # already expanded (e.g. resuming a revise loop)
        prompt = (
            f"Overall goal: \"{state['goal']}\" (category: {state['category']}, difficulty: {state['difficulty']}).\n"
            f"Milestone: \"{milestone['title']}\" — {milestone.get('description', '')}\n\n"
            "Break this milestone into 3-8 concrete, actionable tasks. Each task needs a title, "
            "a short description, a priority (low/medium/high/critical), and an estimated_hours."
        )
        try:
            result: MilestoneTasksResult = model.invoke([
                SystemMessage(content="You are Ora's module-design agent. Tasks must be specific and completable, not vague."),
                HumanMessage(content=prompt),
            ])
            milestone["tasks"] = [t.model_dump() for t in result.tasks]
        except Exception as e:
            logger.exception("expand_node failed for milestone %s", milestone.get("title"))
            return {**state, "error": str(e)}
        # Persist incrementally so a crash mid-expand leaves partial, inspectable progress.
        state = {**state, "milestones": milestones}
        _persist_progress(state, status="generating")

    return state


def critique_node(state: GenerationState) -> dict:
    if state.get("error"):
        return {**state, "approved": False}
    model = _flash_model().with_structured_output(CritiqueResult)
    checklist = {
        "exam_prep": "syllabus coverage, spaced repetition/review milestones, realistic pacing",
        "course": "logical skill progression, prerequisite ordering, a capstone/project milestone",
        "project": "clear deliverables per milestone, realistic scoping, a launch/ship milestone",
    }.get(state["category"], "logical ordering, completeness relative to the goal, realistic scoping")

    prompt = (
        f"Goal: \"{state['goal']}\"\n"
        f"Category: {state['category']}\n"
        f"Review checklist for this category: {checklist}\n\n"
        f"Proposed module structure:\n{json.dumps(state['milestones'], indent=2)}\n\n"
        "Approve only if it genuinely satisfies the checklist and is complete. Otherwise "
        "reject with specific, actionable feedback on what to change."
    )
    try:
        result: CritiqueResult = model.invoke([
            SystemMessage(content="You are a strict reviewer. Do not approve mediocre or incomplete plans."),
            HumanMessage(content=prompt),
        ])
        return {**state, "approved": result.approve, "feedback": result.feedback}
    except Exception as e:
        logger.exception("critique_node failed")
        # Structured-output failure shouldn't block a materialize-able draft — approve as a fallback.
        return {**state, "approved": True, "feedback": f"critique skipped: {e}"}


def materialize_node(state: GenerationState) -> dict:
    status = "ready" if not state.get("error") else "failed"
    _persist_progress(state, status=status, error=state.get("error"))
    return state


def _route_after_critique(state: GenerationState) -> str:
    if state.get("error"):
        return "materialize"
    if state.get("approved"):
        return "materialize"
    if state["critique_round"] >= MAX_CRITIQUE_ROUNDS:
        return "materialize"
    return "revise"


def _bump_round(state: GenerationState) -> dict:
    # Clear tasks on rejected milestones flagged by feedback isn't precise enough to target
    # individual milestones from free-text feedback, so a revise round re-expands everything —
    # bounded by MAX_CRITIQUE_ROUNDS, acceptable cost for correctness over one-shot generation.
    milestones = [{**m, "tasks": []} for m in state["milestones"]]
    return {**state, "milestones": milestones, "critique_round": state["critique_round"] + 1}


_compiled_graph = None


def get_generation_graph():
    global _compiled_graph
    if _compiled_graph is not None:
        return _compiled_graph

    graph = StateGraph(GenerationState)
    graph.add_node("outline", outline_node)
    graph.add_node("expand", expand_node)
    graph.add_node("critique", critique_node)
    graph.add_node("revise", _bump_round)
    graph.add_node("materialize", materialize_node)

    graph.set_entry_point("outline")
    graph.add_edge("outline", "expand")
    graph.add_edge("expand", "critique")
    graph.add_conditional_edges("critique", _route_after_critique, {
        "materialize": "materialize",
        "revise": "revise",
    })
    graph.add_edge("revise", "expand")
    graph.add_edge("materialize", END)

    _compiled_graph = graph.compile()
    return _compiled_graph


def run_generation(module_template_version_id: str, goal: str, category: str, difficulty: str) -> GenerationState:
    """Synchronous entry point — call from a background thread, inside an app context."""
    graph = get_generation_graph()
    initial: GenerationState = {
        "goal": goal,
        "category": category,
        "difficulty": difficulty,
        "module_template_version_id": module_template_version_id,
        "milestones": [],
        "critique_round": 0,
        "approved": False,
        "feedback": None,
        "error": None,
    }
    return graph.invoke(initial)
