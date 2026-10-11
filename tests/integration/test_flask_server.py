"""Integration tests for Flask application endpoints and /api/v1/ routing."""

import io
import json
from unittest.mock import MagicMock
import pytest

from app.server import create_app
from grip import Config, SearchResponse, StreamChunk, SourceItem


@pytest.fixture
def flask_test_app():
    mock_sdk = MagicMock()
    mock_sdk.ready.return_value = (True, "Ready")
    mock_sdk.provider_name = "grip"
    mock_sdk.sessions.count.return_value = 1
    mock_sdk.search.query.return_value = SearchResponse(
        query="test query",
        answer="Answer from Grip SDK",
        sources=[],
    )

    def _stream_gen(*args, **kwargs):
        yield StreamChunk(event="thought", content="Analyzing query...")
        yield StreamChunk(event="delta", content="Answer delta")
        yield StreamChunk(event="done", content="")

    mock_sdk.search.stream.side_effect = _stream_gen

    mock_session = MagicMock()
    mock_session.session_id = "test-session-123"
    mock_session.title = "Test Session"
    mock_session.to_dict.return_value = {
        "id": "test-session-123",
        "title": "Test Session",
        "messages": [],
    }
    mock_session.ask.return_value = SearchResponse(query="hi", answer="Hello back", sources=[])
    mock_session.stream.side_effect = _stream_gen

    mock_sdk.sessions.create.return_value = mock_session
    mock_sdk.sessions.get.return_value = mock_session
    mock_sdk.sessions.list_dicts.return_value = [mock_session.to_dict()]
    mock_sdk.sessions.delete.return_value = True
    mock_sdk.sessions.clear.return_value = 1

    # Rules
    mock_rule = MagicMock()
    mock_rule.to_dict.return_value = {"name": "be_concise", "content": "Be concise", "active": True}
    mock_sdk.rules.to_dict.return_value = [mock_rule.to_dict()]
    mock_sdk.rules.identity = "Grip AI Assistant"
    mock_sdk.rules.response_format = "markdown"
    mock_sdk.rules.compile.return_value = "[SYSTEM] Grip AI"
    mock_sdk.rules.count.return_value = 1
    mock_sdk.rules.list.return_value = [mock_rule]
    mock_sdk.rules.add.return_value = mock_rule
    mock_sdk.rules.toggle.return_value = mock_rule
    mock_sdk.rules.remove.return_value = True

    # Skills
    mock_skill = MagicMock()
    mock_skill.to_dict.return_value = {"name": "summarizer", "description": "Summarizes text"}
    mock_sdk.skills.to_dict.return_value = [mock_skill.to_dict()]
    mock_sdk.skills.count.return_value = 1
    mock_sdk.skills.register.return_value = mock_skill
    mock_sdk.skills.delete.return_value = True

    # Tools
    mock_sdk.tools.to_dict.return_value = [{"name": "calculator", "description": "Calculator"}]
    mock_sdk.tools.call.return_value = 42

    config = Config(port=8000, stream_delay_ms=0)
    app = create_app(config=config, client=mock_sdk)
    app.config["TESTING"] = True
    return app.test_client(), mock_sdk


def test_flask_health_and_verify(flask_test_app):
    client, mock_sdk = flask_test_app

    res = client.get("/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"
    assert data["provider"] == "grip"

    res = client.get("/verify/status")
    assert res.status_code == 200
    assert "ready" in res.get_json()


def test_flask_search_endpoints(flask_test_app):
    client, mock_sdk = flask_test_app

    # Standard /search
    res = client.post("/search", json={"query": "hello world"})
    assert res.status_code == 200
    assert res.get_json()["answer"] == "Answer from Grip SDK"

    # Enterprise /api/v1/search
    res = client.post("/api/v1/search", json={"query": "hello v1"})
    assert res.status_code == 200
    assert res.get_json()["answer"] == "Answer from Grip SDK"


def test_flask_search_stream_endpoints(flask_test_app):
    client, mock_sdk = flask_test_app

    # Standard /search/stream
    res = client.post("/search/stream", json={"query": "stream test"})
    assert res.status_code == 200
    assert "text/event-stream" in res.headers["Content-Type"]
    assert "event: thought" in res.get_data(as_text=True)

    # Enterprise /api/v1/search/stream
    res = client.post("/api/v1/search/stream", json={"query": "stream v1 test"})
    assert res.status_code == 200
    assert "text/event-stream" in res.headers["Content-Type"]


def test_flask_sessions_crud(flask_test_app):
    client, mock_sdk = flask_test_app

    # POST /api/v1/sessions
    res = client.post("/api/v1/sessions", json={"title": "New Chat"})
    assert res.status_code == 201
    assert res.get_json()["session"]["id"] == "test-session-123"

    # GET /api/v1/sessions
    res = client.get("/api/v1/sessions")
    assert res.status_code == 200
    assert len(res.get_json()["sessions"]) == 1

    # GET /api/v1/sessions/<id>
    res = client.get("/api/v1/sessions/test-session-123")
    assert res.status_code == 200
    assert res.get_json()["id"] == "test-session-123"

    # POST /api/v1/sessions/<id>/ask
    res = client.post("/api/v1/sessions/test-session-123/ask", json={"query": "hi"})
    assert res.status_code == 200

    # POST /api/v1/sessions/<id>/stream
    res = client.post("/api/v1/sessions/test-session-123/stream", json={"query": "hi stream"})
    assert res.status_code == 200
    assert "text/event-stream" in res.headers["Content-Type"]

    # DELETE /api/v1/sessions/<id>
    res = client.delete("/api/v1/sessions/test-session-123")
    assert res.status_code == 200
    assert res.get_json()["deleted"] is True

    # POST /api/v1/sessions/clear
    res = client.post("/api/v1/sessions/clear")
    assert res.status_code == 200
    assert res.get_json()["cleared"] is True


def test_flask_rules_and_skills_endpoints(flask_test_app):
    client, mock_sdk = flask_test_app

    # Rules
    res = client.get("/api/v1/rules")
    assert res.status_code == 200
    assert res.get_json()["identity"] == "Grip AI Assistant"

    res = client.post("/api/v1/rules", json={"name": "test_rule", "content": "Rule text"})
    assert res.status_code == 201

    res = client.post("/api/v1/rules/system", json={"identity": "New Identity", "response_format": "json"})
    assert res.status_code == 200

    res = client.post("/api/v1/rules/test_rule/toggle", json={"active": False})
    assert res.status_code == 200

    res = client.delete("/api/v1/rules/test_rule")
    assert res.status_code == 200

    # Skills
    res = client.get("/api/v1/skills")
    assert res.status_code == 200

    res = client.post("/api/v1/skills", json={"name": "summarizer", "instructions": "Summarize concisely"})
    assert res.status_code == 201

    res = client.delete("/api/v1/skills/summarizer")
    assert res.status_code == 200

    # Tools
    res = client.get("/api/v1/tools")
    assert res.status_code == 200

    res = client.post("/api/v1/tools/call", json={"name": "calculator", "args": {"expression": "2+2"}})
    assert res.status_code == 200
    assert res.get_json()["result"] == 42


def test_flask_upload_file(flask_test_app):
    client, mock_sdk = flask_test_app

    file_data = (io.BytesIO(b"Hello world from test file!"), "test.txt")
    res = client.post("/api/v1/upload", data={"file": file_data}, content_type="multipart/form-data")
    assert res.status_code == 201
    assert res.get_json()["filename"] == "test.txt"
    assert "Hello world" in res.get_json()["content"]
