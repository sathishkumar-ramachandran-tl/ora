"""Core Intelligence Layer (graph_v2) tests — mocked structured-output LLM calls (no
live API key needed), validating the classify->direct / classify->planner->executor->
reflect recursive control flow, bounded replanning, and delegation to the existing
Planning Cortex for explicit multi-turn roadmap requests.
"""
from unittest.mock import patch

from langchain_core.messages import HumanMessage, AIMessage

from app.agents import graph_v2
from app.agents.state import ScratchpadState


class _FakeStructuredModel:
    """Returned by `<model>.with_structured_output(schema)` — .invoke() ignores the
    prompt/config and returns a canned response, optionally varying per call."""

    def __init__(self, response):
        self.response = response
        self.call_count = 0

    def invoke(self, messages, config=None):
        result = self.response(self.call_count) if callable(self.response) else self.response
        self.call_count += 1
        return result


class _FakeChatModel:
    """Stands in for a plain (non-structured) `.invoke()` call, e.g. classify_node's
    intent classification."""

    def __init__(self, text):
        self.text = text

    def invoke(self, messages, config=None):
        return AIMessage(content=self.text)

    def with_structured_output(self, schema):
        return _FakeStructuredModel(self.response) if hasattr(self, "response") else _FakeStructuredModel(None)


class _FakeAgent:
    """Stands in for a compiled create_react_agent — .invoke() ignores tools entirely
    and returns a canned final AI message."""

    def __init__(self, reply_text):
        self.reply_text = reply_text

    def invoke(self, inputs, config=None):
        return {"messages": inputs["messages"] + [AIMessage(content=self.reply_text)]}


def _base_state(**overrides) -> ScratchpadState:
    state = {
        "messages": [HumanMessage(content="do something")],
        "workspace_id": "ws1",
        "user_id": "u1",
        "workspace_context": {},
        "complexity": None,
        "goal": None,
        "plan": [],
        "working_memory": {},
        "current_step_index": 0,
        "replan_count": 0,
        "next_action": None,
        "final_answer": None,
        "planning_phase": None,
        "draft_plan": {},
        "planning_project_id": None,
    }
    state.update(overrides)
    return state


# ---------------------------------------------------------------------------
# classify_node
# ---------------------------------------------------------------------------

def test_classify_routes_direct():
    state = _base_state(messages=[HumanMessage(content="list my tasks")])
    with patch.object(graph_v2, "_flash_model", return_value=_FakeChatModel("direct")):
        result = graph_v2.classify_node(state, {})
    assert result["complexity"] == "direct"
    assert graph_v2._route_after_classify({**state, **result}) == "direct"


def test_classify_routes_agentic():
    state = _base_state(messages=[HumanMessage(content="create onboarding tasks and schedule focus blocks")])
    with patch.object(graph_v2, "_flash_model", return_value=_FakeChatModel("agentic")):
        result = graph_v2.classify_node(state, {})
    assert result["complexity"] == "agentic"
    assert graph_v2._route_after_classify({**state, **result}) == "agentic"


def test_classify_mid_planning_session_forces_plan_without_llm_call():
    state = _base_state(planning_phase="drafting")
    # No _flash_model patch — a real call would fail without an API key, proving the
    # early-return path is actually taken.
    result = graph_v2.classify_node(state, {})
    assert result == {"complexity": "plan"}


def test_classify_falls_back_to_direct_on_bad_llm_output():
    state = _base_state()
    with patch.object(graph_v2, "_flash_model", return_value=_FakeChatModel("nonsense reply")):
        result = graph_v2.classify_node(state, {})
    assert result["complexity"] == "direct"


# ---------------------------------------------------------------------------
# planner_node
# ---------------------------------------------------------------------------

def test_planner_produces_bounded_multistep_plan():
    steps = graph_v2.SubTaskPlan(steps=[
        graph_v2.PlanStepSpec(description="Look up the target project"),
        graph_v2.PlanStepSpec(description="Create the onboarding tasks"),
        graph_v2.PlanStepSpec(description="Schedule focus blocks for them"),
    ])
    fake_model = _FakeChatModel("")
    fake_model.response = steps  # picked up by with_structured_output()

    state = _base_state(goal="set up onboarding")
    with patch.object(graph_v2, "_pro_model", return_value=fake_model):
        result = graph_v2.planner_node(state, {})

    assert len(result["plan"]) == 3
    assert result["plan"][0]["status"] == "pending"
    assert result["current_step_index"] == 0
    assert result["goal"] == "set up onboarding"


def test_planner_truncates_to_max_steps():
    too_many = graph_v2.SubTaskPlan(steps=[
        graph_v2.PlanStepSpec(description=f"Step {i}") for i in range(10)
    ])
    fake_model = _FakeChatModel("")
    fake_model.response = too_many

    state = _base_state(goal="a huge goal")
    with patch.object(graph_v2, "_pro_model", return_value=fake_model):
        result = graph_v2.planner_node(state, {})

    assert len(result["plan"]) == graph_v2.MAX_PLAN_STEPS


def test_planner_falls_back_to_single_step_on_error():
    class BrokenModel:
        def with_structured_output(self, schema):
            class _Broken:
                def invoke(self, messages, config=None):
                    raise RuntimeError("provider unavailable")
            return _Broken()

    state = _base_state(goal="do the thing")
    with patch.object(graph_v2, "_pro_model", return_value=BrokenModel()):
        result = graph_v2.planner_node(state, {})

    assert len(result["plan"]) == 1
    assert result["plan"][0]["description"] == "do the thing"


# ---------------------------------------------------------------------------
# executor_node
# ---------------------------------------------------------------------------

def test_executor_runs_current_step_and_updates_working_memory():
    plan = [
        {"id": 0, "description": "Step one", "status": "pending", "result": None},
        {"id": 1, "description": "Step two", "status": "pending", "result": None},
    ]
    state = _base_state(goal="goal", plan=plan, current_step_index=0)

    with patch.object(graph_v2, "build_executor_agent", return_value=_FakeAgent("Created task T1 (id=t1).")):
        result = graph_v2.executor_node(state, {})

    assert result["plan"][0]["status"] == "done"
    assert "Created task T1" in result["plan"][0]["result"]
    assert result["plan"][1]["status"] == "pending"  # untouched
    assert result["working_memory"]["step_1"] == "Created task T1 (id=t1)."


def test_executor_marks_step_failed_on_exception():
    plan = [{"id": 0, "description": "Step one", "status": "pending", "result": None}]
    state = _base_state(goal="goal", plan=plan, current_step_index=0)

    class _BrokenAgent:
        def invoke(self, inputs, config=None):
            raise RuntimeError("tool exploded")

    with patch.object(graph_v2, "build_executor_agent", return_value=_BrokenAgent()):
        result = graph_v2.executor_node(state, {})

    assert result["plan"][0]["status"] == "failed"
    assert "tool exploded" in result["plan"][0]["result"]


# ---------------------------------------------------------------------------
# reflect_node + routing
# ---------------------------------------------------------------------------

def test_reflect_continues_when_steps_remain():
    plan = [
        {"id": 0, "description": "Step one", "status": "done", "result": "did it"},
        {"id": 1, "description": "Step two", "status": "pending", "result": None},
    ]
    state = _base_state(plan=plan, current_step_index=0)
    fake_model = _FakeChatModel("")
    fake_model.response = graph_v2.ReflectDecision(action="continue")

    with patch.object(graph_v2, "_flash_model", return_value=fake_model):
        result = graph_v2.reflect_node(state, {})

    assert result["next_action"] == "continue"
    assert result["current_step_index"] == 1
    assert graph_v2._route_after_reflect({**state, **result}) == "executor"


def test_reflect_forces_done_when_no_steps_remain_even_if_model_says_continue():
    plan = [{"id": 0, "description": "Only step", "status": "done", "result": "did it"}]
    state = _base_state(plan=plan, current_step_index=0)
    fake_model = _FakeChatModel("")
    fake_model.response = graph_v2.ReflectDecision(action="continue")  # model is "wrong" here

    with patch.object(graph_v2, "_flash_model", return_value=fake_model):
        result = graph_v2.reflect_node(state, {})

    assert result["next_action"] == "done"
    assert result["final_answer"]
    assert graph_v2._route_after_reflect({**state, **result}) == "end"


def test_reflect_replan_is_bounded_by_max_replans():
    plan = [{"id": 0, "description": "Bad step", "status": "failed", "result": "boom"}]
    fake_model = _FakeChatModel("")
    fake_model.response = graph_v2.ReflectDecision(action="replan", replan_reason="step failed")

    # Under the bound -> route to planner
    state = _base_state(plan=plan, current_step_index=0, replan_count=0)
    with patch.object(graph_v2, "_flash_model", return_value=fake_model):
        result = graph_v2.reflect_node(state, {})
    assert result["replan_count"] == 1
    assert graph_v2._route_after_reflect({**state, **result}) == "planner"

    # Past the bound -> bail out to end instead of looping forever
    state = _base_state(plan=plan, current_step_index=0, replan_count=graph_v2.MAX_REPLANS + 1)
    with patch.object(graph_v2, "_flash_model", return_value=fake_model):
        result = graph_v2.reflect_node(state, {})
    assert graph_v2._route_after_reflect({**state, **result}) == "end"


# ---------------------------------------------------------------------------
# Full graph — proves genuine multi-step recursion (planner runs once, executor
# runs more than once before END), per the roadmap's Phase-2 verification bullet.
# ---------------------------------------------------------------------------

def test_full_graph_runs_executor_twice_for_a_two_step_plan(app):
    two_steps = graph_v2.SubTaskPlan(steps=[
        graph_v2.PlanStepSpec(description="Step one"),
        graph_v2.PlanStepSpec(description="Step two"),
    ])
    planner_model = _FakeChatModel("")
    planner_model.response = two_steps

    reflect_responses = iter([
        graph_v2.ReflectDecision(action="continue"),
        graph_v2.ReflectDecision(action="done", final_answer="✓ Both steps complete."),
    ])
    reflect_model = _FakeChatModel("")
    reflect_model.response = lambda _n: next(reflect_responses)

    executor_calls = {"n": 0}

    class _CountingAgent:
        def invoke(self, inputs, config=None):
            executor_calls["n"] += 1
            return {"messages": inputs["messages"] + [AIMessage(content=f"did step {executor_calls['n']}")]}

    with app.app_context():
        with patch.object(graph_v2, "_flash_model", side_effect=[
                 _FakeChatModel("agentic"),  # classify
                 reflect_model,              # reflect after step 1
                 reflect_model,              # reflect after step 2
             ]), \
             patch.object(graph_v2, "_pro_model", return_value=planner_model), \
             patch.object(graph_v2, "build_executor_agent", return_value=_CountingAgent()):

            graph = graph_v2.create_orchestrator()
            final_state = graph.invoke(
                _base_state(messages=[HumanMessage(content="do a two-step thing")]),
                config={"configurable": {"thread_id": "test-thread-1"}, "recursion_limit": 50},
            )

    assert executor_calls["n"] == 2  # executor genuinely ran more than once
    assert len(final_state["plan"]) == 2
    assert all(s["status"] == "done" for s in final_state["plan"])
    assert final_state["final_answer"] == "✓ Both steps complete."
