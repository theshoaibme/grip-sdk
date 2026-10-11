"""Integration tests for FastAPI REST and SSE endpoints."""

from unittest.mock import MagicMock
import pytest
from starlette.testclient import TestClient

from services.api.app.main import app
from services.api.app.dependencies import get_engine, get_session_store
from grip_core.models.response import SearchResponse, SourceItem, StreamChunk
from grip_engine.engine import GripEngine


@pytest.fixture
def mock_engine():
    engine = MagicMock(spec=GripEngine)
    engine.ready.return_value = (True, "Ready")
    engine.registry = MagicMock()
    engine.registry.list_providers.return_value = ["google", "openai"]
    engine.name = "google"

    engine.search.return_value = SearchResponse(
        query="test query",
        answer="Integration test response answer",
        sources=[SourceItem(title="Doc 1", url="https://example.com/doc1")],
        status="success",
    )

    def _mock_stream(*args, **kwargs):
        yield StreamChunk(event="delta", delta="Chunk 1 ")
        yield StreamChunk(event="delta", delta="Chunk 2")

    engine.stream_search.side_effect = _mock_stream

    mock_store = MagicMock()
    mock_session = MagicMock()
    mock_session.session_id = "test-session-1"
    mock_session.title = "Test Session"
    mock_session.created_at = "2026-10-12T00:00:00Z"
    mock_session.updated_at = "2026-10-12T00:00:00Z"
    mock_session.messages = []
    mock_session.metadata = {}
    mock_session.to_dict.return_value = {
        "session_id": "test-session-1",
        "title": "Test Session",
        "created_at": "2026-10-12T00:00:00Z",
        "updated_at": "2026-10-12T00:00:00Z",
        "messages": [],
        "metadata": {},
    }

    mock_store.create_session.return_value = mock_session
    mock_store.list_sessions.return_value = [mock_session]
    mock_store.get_session.return_value = mock_session
    mock_store.delete_session.return_value = True
    mock_store.clear_all.return_value = 1

    engine.session_store = mock_store
    return engine


def test_api_health_endpoint(mock_engine):
    app.dependency_overrides[get_engine] = lambda: mock_engine
    with TestClient(app) as client:
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["ready"] is True
        assert data["status"] == "healthy"
        assert "google" in data["active_providers"]
    app.dependency_overrides.clear()


def test_api_search_endpoint(mock_engine):
    app.dependency_overrides[get_engine] = lambda: mock_engine
    with TestClient(app) as client:
        res = client.post("/api/v1/search", json={"query": "test query", "provider": "google"})
        assert res.status_code == 200
        data = res.json()
        assert data["answer"] == "Integration test response answer"
        assert len(data["sources"]) == 1
    app.dependency_overrides.clear()


def test_api_stream_endpoint(mock_engine):
    app.dependency_overrides[get_engine] = lambda: mock_engine
    with TestClient(app) as client:
        res = client.post("/api/v1/search/stream", json={"query": "stream test"})
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]
        assert "Chunk 1" in res.text
    app.dependency_overrides.clear()


def test_api_sessions_crud(mock_engine):
    app.dependency_overrides[get_engine] = lambda: mock_engine
    app.dependency_overrides[get_session_store] = lambda: mock_engine.session_store
    with TestClient(app) as client:
        # Create
        res = client.post("/api/v1/sessions", json={"title": "Test Session"})
        assert res.status_code == 200
        assert res.json()["session_id"] == "test-session-1"

        # List
        res = client.get("/api/v1/sessions")
        assert res.status_code == 200
        assert len(res.json()["sessions"]) == 1

        # Delete
        res = client.delete("/api/v1/sessions/test-session-1")
        assert res.status_code == 200

        # Clear
        res = client.post("/api/v1/sessions/clear")
        assert res.status_code == 200
        assert res.json()["cleared"] == 1
    app.dependency_overrides.clear()
