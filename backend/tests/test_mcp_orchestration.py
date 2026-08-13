from langchain_core.messages import AIMessage

from app import models
from app import mcp_server
from app.agents.control_plane import AgentRunStatus


class _FakeOrchestrator:
    def __init__(self, captured):
        self._captured = captured

    def invoke(self, state, config=None):
        self._captured["state"] = state
        self._captured["config"] = config
        return {"messages": [AIMessage(content="ok from v2")]}


def test_mcp_chat_uses_graph_v2_by_default(db, monkeypatch):
    user = models.User(id="u1", email="u1@example.com", name="User One")
    ws = models.Workspace(id="ws1", name="WS 1", context="personal", type="project", owner_id="u1")
    db.session.add_all([user, ws])
    db.session.commit()

    captured = {}
    monkeypatch.delenv("AGENT_ENGINE", raising=False)
    monkeypatch.setitem(mcp_server._config, "workspace_id", "ws1")
    monkeypatch.setitem(mcp_server._config, "user_id", "u1")
    monkeypatch.setattr(
        "app.agents.graph_v2.create_orchestrator",
        lambda: _FakeOrchestrator(captured),
    )
    monkeypatch.setattr(
        "app.agents.orchestrator.create_orchestrator",
        lambda: (_ for _ in ()).throw(AssertionError("v1 orchestrator should not be used by default")),
    )

    result = mcp_server._run_chat("hello", "mcp-test-session")

    assert result == {"session_id": "mcp-test-session", "response": "ok from v2"}
    assert "complexity" in captured["state"]
    assert "intent" not in captured["state"]
    run = models.AgentRun.query.filter_by(session_id="mcp-test-session").one()
    assert run.status == AgentRunStatus.COMPLETED.value
