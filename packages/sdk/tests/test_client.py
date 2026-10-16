"""Tests for Grip synchronous client."""

from unittest.mock import MagicMock
import pytest

from grip import Grip, SearchResponse, SourceItem, StreamChunk
from grip_core.models.session import SessionDetail


def test_grip_client_initialization():
    client = Grip()
    assert client.provider == "google"
    assert client.search is not None
    assert client.sessions is not None
    assert client.rules is not None


def test_grip_client_query_with_mock():
    mock_engine = MagicMock()
    mock_engine.search.return_value = SearchResponse(
        answer="Paris is the capital of France.",
        sources=[SourceItem(title="France Info", link="https://example.com/france")],
        query="capital of france",
        status="success",
    )

    client = Grip(engine=mock_engine)
    res = client.query("capital of france")

    assert res.answer == "Paris is the capital of France."
    assert len(res.sources) == 1
    assert res.sources[0].title == "France Info"
    mock_engine.search.assert_called_once()


def test_grip_client_stream_with_mock():
    mock_engine = MagicMock()
    mock_engine.stream_search.return_value = iter([
        StreamChunk(type="delta", delta="Hello "),
        StreamChunk(type="delta", delta="World!"),
    ])

    client = Grip(engine=mock_engine)
    chunks = list(client.stream("Say hello"))

    assert len(chunks) == 2
    assert chunks[0].delta == "Hello "
    assert chunks[1].delta == "World!"


def test_grip_client_sessions_with_mock():
    mock_engine = MagicMock()
    mock_store = MagicMock()
    mock_session = MagicMock()
    mock_session.session_id = "sess-123"
    mock_session.title = "Test Session"
    mock_session.created_at = "2026-10-12T00:00:00Z"
    mock_session.updated_at = "2026-10-12T00:00:00Z"
    mock_session.messages = []
    mock_session.metadata = {}

    mock_store.create_session.return_value = mock_session
    mock_store.get_session.return_value = mock_session
    mock_store.list_sessions.return_value = [mock_session]
    mock_store.delete_session.return_value = True
    mock_store.clear_all.return_value = 1

    mock_engine.session_store = mock_store
    client = Grip(engine=mock_engine)

    sess = client.create_session(title="Test Session")
    assert sess.session_id == "sess-123"

    retrieved = client.get_session("sess-123")
    assert retrieved is not None
    assert retrieved.session_id == "sess-123"

    listed = client.list_sessions()
    assert len(listed) == 1

    assert client.delete_session("sess-123") is True
    assert client.clear_sessions() == 1
