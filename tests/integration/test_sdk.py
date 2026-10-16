"""Comprehensive Integration tests for Grip SDK end-to-end client."""

import asyncio
import json
from unittest.mock import MagicMock
import pytest
import responses

from grip import Grip, AsyncGrip, SearchResponse, SourceItem, StreamChunk
from grip.cli.main import main as cli_main
from core.errors import ProviderError
from core.models.session import SessionDetail, SessionSummary


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


def test_sdk_stream_chunks_embedded():
    mock_engine = MagicMock()
    mock_engine.stream_search.return_value = iter([
        {"event": "thinking", "thinking": "Analyzing physics papers..."},
        {"event": "delta", "delta": "Quantum "},
        {"event": "delta", "delta": "teleportation is possible."},
        {"event": "done", "response": {"answer": "Quantum teleportation is possible."}},
    ])

    client = Grip(engine=mock_engine)
    chunks = list(client.stream("Explain teleportation"))
    assert len(chunks) == 4

    assert chunks[0].event == "thinking"
    assert chunks[0].thinking == "Analyzing physics papers..."
    # Verify dict compatibility on StreamChunk
    assert chunks[0]["event"] == "thinking"
    assert chunks[0].get("thinking") == "Analyzing physics papers..."

    deltas = [c.delta for c in chunks if c.event == "delta"]
    assert "".join(deltas) == "Quantum teleportation is possible."


@responses.activate
def test_sdk_remote_http_mode_search():
    api_url = "http://api.grip.test"
    responses.add(
        responses.POST,
        f"{api_url}/api/v1/search",
        json={
            "query": "superconductivity",
            "answer": "Zero electrical resistance.",
            "sources": [{"title": "Science Direct", "url": "https://example.com/sc"}],
            "provider": "google",
            "status": "success",
            "metadata": {"search_time": 0.42},
        },
        status=200,
    )

    client = Grip(base_url=api_url, api_key="secret-key")
    res = client.query("superconductivity")

    assert res.answer == "Zero electrical resistance."
    assert len(res.sources) == 1
    assert res.sources[0].title == "Science Direct"
    assert res.metadata.search_time == 0.42


@responses.activate
def test_sdk_remote_http_mode_stream():
    api_url = "http://api.grip.test"
    sse_body = (
        'data: {"type": "thinking", "content": "Thinking about cold fusion..."}\n\n'
        'data: {"type": "delta", "delta": "Fusion "}\n\n'
        'data: {"type": "delta", "delta": "energy is clean."}\n\n'
    )
    responses.add(
        responses.POST,
        f"{api_url}/api/v1/search/stream",
        body=sse_body,
        content_type="text/event-stream",
        status=200,
    )

    client = Grip(base_url=api_url)
    chunks = list(client.stream("cold fusion"))
    assert len(chunks) == 3
    assert chunks[0].type == "thinking"
    assert "".join([c.delta for c in chunks if c.type == "delta"]) == "Fusion energy is clean."


@responses.activate
def test_sdk_remote_http_mode_sessions_crud():
    api_url = "http://api.grip.test"
    # Create
    responses.add(
        responses.POST,
        f"{api_url}/api/v1/sessions",
        json={
            "session_id": "sess-remote-1",
            "title": "Remote Session",
            "created_at": "2026-10-12T00:00:00Z",
            "updated_at": "2026-10-12T00:00:00Z",
            "messages": [],
            "metadata": {},
        },
        status=200,
    )
    # Get
    responses.add(
        responses.GET,
        f"{api_url}/api/v1/sessions/sess-remote-1",
        json={
            "session_id": "sess-remote-1",
            "title": "Remote Session",
            "created_at": "2026-10-12T00:00:00Z",
            "updated_at": "2026-10-12T00:00:00Z",
            "messages": [],
            "metadata": {},
        },
        status=200,
    )
    # List
    responses.add(
        responses.GET,
        f"{api_url}/api/v1/sessions",
        json=[
            {
                "session_id": "sess-remote-1",
                "title": "Remote Session",
                "message_count": 0,
                "created_at": "2026-10-12T00:00:00Z",
                "updated_at": "2026-10-12T00:00:00Z",
            }
        ],
        status=200,
    )
    # Delete
    responses.add(
        responses.DELETE,
        f"{api_url}/api/v1/sessions/sess-remote-1",
        json={"success": True},
        status=200,
    )

    client = Grip(base_url=api_url)
    s = client.create_session(title="Remote Session")
    assert s.session_id == "sess-remote-1"

    fetched = client.get_session("sess-remote-1")
    assert fetched.title == "Remote Session"

    all_sess = client.list_sessions()
    assert len(all_sess) == 1

    deleted = client.delete_session("sess-remote-1")
    assert deleted is True


@responses.activate
def test_sdk_remote_error_handling():
    api_url = "http://api.grip.test"
    responses.add(
        responses.POST,
        f"{api_url}/api/v1/search",
        json={"detail": "Internal server error"},
        status=500,
    )

    client = Grip(base_url=api_url)
    with pytest.raises(ProviderError):
        client.query("fail query")


def test_sdk_context_managers():
    with Grip() as client:
        assert client.provider == "google"

    async def _test_async():
        async with AsyncGrip() as aclient:
            assert aclient.provider == "google"

    asyncio.run(_test_async())


def test_sdk_cli_commands(capsys):
    from grip import __version__
    # Test --version
    with pytest.raises(SystemExit):
        cli_main(["--version"])
    out, _ = capsys.readouterr()
    assert __version__ in out


    # Test providers command
    ret = cli_main(["providers"])
    assert ret == 0
    out, _ = capsys.readouterr()
    assert "Registered AI Search Providers" in out
    assert "google" in out

    # Test rules command
    ret = cli_main(["rules", "--add", "Keep answers concise", "--list"])
    assert ret == 0
    out, _ = capsys.readouterr()
    assert "Keep answers concise" in out
