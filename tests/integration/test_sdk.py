"""Integration tests for Grip SDK end-to-end client."""

from unittest.mock import MagicMock
import pytest

from grip import Grip, SearchResponse, SourceItem, StreamChunk


def test_sdk_full_search_cycle():
    mock_engine = MagicMock()
    mock_engine.search.return_value = SearchResponse(
        query="quantum entanglement",
        answer="Quantum entanglement occurs when particles become inextricably linked.",
        sources=[SourceItem(title="Nature Physics", url="https://nature.com/physics")],
        status="success",
        provider="google",
    )
    from grip_engine.agent.rules import RulesRegistry
    from grip_engine.agent.skills import SkillsRegistry
    from grip_engine.tools.builtin import ToolRegistry
    mock_engine.rules = RulesRegistry()
    mock_engine.skills = SkillsRegistry()
    mock_engine.tools = ToolRegistry()

    client = Grip(engine=mock_engine)

    # 1. Search query
    res = client.query("quantum entanglement")
    assert res.provider == "google"
    assert "entanglement" in res.answer
    assert len(res.sources) == 1

    # 2. Rule configuration
    rule = client.rules.add("Always cite scientific journals")
    assert rule.name is not None
    assert len(client.rules.list()) >= 1

    # 3. Custom tool registration
    @client.tool(description="Calculate double")
    def double_value(x: int) -> int:
        return x * 2

    assert "double_value" in client.tools
    assert client.tools.call("double_value", x=21) == 42


def test_sdk_multi_turn_session():
    mock_engine = MagicMock()
    mock_store = MagicMock()
    mock_session = MagicMock()
    mock_session.session_id = "session-quantum"
    mock_session.title = "Physics Q&A"
    mock_session.created_at = "2026-10-12T00:00:00Z"
    mock_session.updated_at = "2026-10-12T00:00:00Z"
    mock_session.messages = []
    mock_session.metadata = {}

    mock_store.create_session.return_value = mock_session
    mock_store.get_session.return_value = mock_session
    mock_store.list_sessions.return_value = [mock_session]
    mock_store.delete_session.return_value = True

    mock_engine.session_store = mock_store
    mock_engine.search.return_value = SearchResponse(
        query="Follow up on entanglement",
        answer="Particles remain correlated regardless of distance.",
        session_id="session-quantum",
    )

    client = Grip(engine=mock_engine)
    session = client.create_session(title="Physics Q&A")
    assert session.session_id == "session-quantum"

    ans = client.chat("Follow up on entanglement", session_id=session.session_id)
    assert "correlated" in ans.answer
