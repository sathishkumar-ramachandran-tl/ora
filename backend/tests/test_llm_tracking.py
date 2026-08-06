"""Verifies every LLM call made through the orchestrator is logged as an LlmCall
row with token usage — the observability requirement, not just the routing logic."""
from typing import List, Optional
from unittest.mock import patch

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatGeneration, ChatResult

from app.agents import orchestrator
from app.agents.models import LlmCall


class FakeChatModel(BaseChatModel):
    """Minimal fake chat model that reports token usage like a real provider would."""

    reply: str = "query"

    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None, run_manager=None, **kwargs) -> ChatResult:
        message = AIMessage(
            content=self.reply,
            usage_metadata={"input_tokens": 12, "output_tokens": 3, "total_tokens": 15},
        )
        return ChatResult(generations=[ChatGeneration(message=message)])

    @property
    def _llm_type(self) -> str:
        return "fake"


def test_router_node_logs_llm_call(app, db):
    with app.app_context():
        with patch.object(orchestrator, "_flash_model", return_value=FakeChatModel()):
            state = {
                "messages": [orchestrator.HumanMessage(content="list my tasks")],
                "workspace_id": None,
                "user_id": None,
                "planning_phase": None,
            }
            config = {"configurable": {"thread_id": "session-123"}}

            result = orchestrator.router_node(state, config)

        assert result["intent"] == "query"

        rows = LlmCall.query.filter_by(session_id="session-123").all()
        assert len(rows) == 1
        row = rows[0]
        assert row.node == "router"
        assert row.model == orchestrator.FLASH_MODEL_NAME
        assert row.prompt_tokens == 12
        assert row.completion_tokens == 3
        assert row.total_tokens == 15
        assert row.status == "success"
        assert row.estimated_cost_usd >= 0


def test_router_node_logs_error_on_llm_failure(app, db):
    class BrokenChatModel(FakeChatModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            raise RuntimeError("provider unavailable")

    with app.app_context():
        with patch.object(orchestrator, "_flash_model", return_value=BrokenChatModel()):
            state = {
                "messages": [orchestrator.HumanMessage(content="hello")],
                "workspace_id": None,
                "user_id": None,
                "planning_phase": None,
            }
            config = {"configurable": {"thread_id": "session-err"}}

            result = orchestrator.router_node(state, config)

        # router_node swallows LLM errors and falls back to 'query'
        assert result["intent"] == "query"

        rows = LlmCall.query.filter_by(session_id="session-err").all()
        assert len(rows) == 1
        assert rows[0].status == "error"
        assert "provider unavailable" in rows[0].error_message
