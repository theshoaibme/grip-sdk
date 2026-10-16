"""Tests for Grip SDK Production Readiness Features:
- Retries and connection pooling
- Granular timeouts and request IDs
- Typed exceptions (APIStatusError, AuthenticationError, RateLimitError, APITimeoutError, etc.)
- Dictionary access ergonomics on response models
- Multi-provider fallback failover
- Real-time async streaming
- Resource cleanup and context management
"""

import asyncio
import pytest
import responses
from unittest.mock import MagicMock

import grip
from grip.exceptions import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    NotFoundError,
    ProviderError,
    RateLimitError,
)
from core.models.response import Metadata, SearchResponse, StreamChunk
from core.models.session import SessionDetail, SessionMessage
from core.models.source import SourceItem


def test_response_models_dict_access_ergonomics():
    """Verify that models support both attribute and dictionary-style access."""
    source = SourceItem(title="Quantum AI", url="https://example.com/quantum", snippet="Breakthroughs in QAI")
    assert source["title"] == "Quantum AI"
    assert source.get("url") == "https://example.com/quantum"
    assert source.get("nonexistent", "default") == "default"
    assert "snippet" in source

    meta = Metadata(latency=0.45, provider="google", request_id="req_test_123")
    assert meta["latency"] == 0.45
    assert meta["request_id"] == "req_test_123"
    assert "provider" in meta

    resp = SearchResponse(
        answer="Quantum computing uses qubits.",
        sources=[source],
        query="quantum computing",
        metadata=meta,
    )
    # Attribute access
    assert resp.answer == "Quantum computing uses qubits."
    assert resp.metadata.provider == "google"

    # Dictionary access
    assert resp["answer"] == "Quantum computing uses qubits."
    assert resp["query"] == "quantum computing"
    assert len(resp["sources"]) == 1
    assert resp["sources"][0]["title"] == "Quantum AI"
    assert resp.get("status") == "success"
    assert "answer" in resp
    assert "invalid_key" not in resp

    # Dict keys, items, values
    keys = list(resp.keys())
    assert "answer" in keys
    assert "sources" in keys
    assert ("answer", "Quantum computing uses qubits.") in list(resp.items())


def test_session_models_dict_access_ergonomics():
    msg = SessionMessage(role="user", content="Hello Grip")
    assert msg["role"] == "user"
    assert msg["content"] == "Hello Grip"
    assert "role" in msg

    sess = SessionDetail(
        session_id="sess_prod_1",
        title="Prod Session",
        messages=[msg],
        metadata={"env": "production"},
    )
    assert sess["session_id"] == "sess_prod_1"
    assert sess["title"] == "Prod Session"
    assert sess.get("metadata")["env"] == "production"


@responses.activate
def test_remote_http_typed_error_mapping():
    base_url = "http://api.grip-test.internal"
    client = grip.Grip(base_url=base_url, max_retries=0)

    # 401 -> AuthenticationError
    responses.add(
        responses.POST,
        f"{base_url}/api/v1/search",
        json={"error": {"message": "Invalid API Key"}},
        status=401,
        headers={"X-Request-ID": "req_auth_fail"},
    )
    with pytest.raises(AuthenticationError) as exc_info:
        client.query("Test query")
    assert "Authentication failed" in str(exc_info.value)

    # 404 -> NotFoundError
    responses.add(
        responses.POST,
        f"{base_url}/api/v1/search",
        json={"error": {"message": "Endpoint or model not found"}},
        status=404,
    )
    with pytest.raises(NotFoundError):
        client.query("Test query")

    # 429 -> RateLimitError
    responses.add(
        responses.POST,
        f"{base_url}/api/v1/search",
        json={"error": {"message": "Rate limit quota exceeded"}},
        status=429,
    )
    with pytest.raises(RateLimitError):
        client.query("Test query")

    # 500 -> APIStatusError with status_code, body, and request_id
    responses.add(
        responses.POST,
        f"{base_url}/api/v1/search",
        json={"error": {"message": "Internal gateway error"}},
        status=500,
        headers={"X-Request-ID": "req_server_err_99"},
    )
    with pytest.raises(APIStatusError) as exc_info:
        client.query("Test query")
    assert exc_info.value.status_code == 500
    assert exc_info.value.request_id == "req_server_err_99"


@responses.activate
def test_remote_http_request_id_and_timeout():
    base_url = "http://api.grip-test.internal"
    client = grip.Grip(base_url=base_url, max_retries=0)

    responses.add(
        responses.POST,
        f"{base_url}/api/v1/search",
        json={
            "answer": "Grip is enterprise AI search",
            "sources": [],
            "metadata": {"latency": 0.2, "provider": "google"},
            "query": "What is Grip?",
            "status": "success",
        },
        status=200,
        headers={"X-Request-ID": "req_upstream_server_42"},
    )

    resp = client.query("What is Grip?", timeout=(5.0, 30.0))
    assert resp.answer == "Grip is enterprise AI search"
    assert resp.metadata.request_id == "req_upstream_server_42"

    # Check request headers sent
    assert len(responses.calls) == 1
    sent_request = responses.calls[0].request
    assert sent_request.headers.get("X-Request-ID", "").startswith("req_")


@responses.activate
def test_multi_provider_fallback_remote():
    base_url = "http://api.grip-test.internal"
    client = grip.Grip(base_url=base_url, max_retries=0)

    # First call to primary provider fails with 503
    responses.add(
        responses.POST,
        f"{base_url}/api/v1/search",
        json={"error": {"message": "Primary provider overloaded"}},
        status=503,
    )
    # Second call with fallback provider succeeds
    responses.add(
        responses.POST,
        f"{base_url}/api/v1/search",
        json={
            "answer": "Fallback response from OpenAI",
            "sources": [],
            "metadata": {"provider": "openai"},
            "query": "Failover query",
            "status": "success",
        },
        status=200,
    )

    resp = client.query(
        "Failover query",
        provider="google",
        fallback=["openai"],
    )
    assert resp.answer == "Fallback response from OpenAI"
    assert len(responses.calls) == 2


def test_multi_provider_fallback_embedded():
    mock_engine = MagicMock()

    # Call 1 fails, Call 2 succeeds
    def mock_search(query, provider, **kwargs):
        if provider == "failing_provider":
            raise ProviderError("failing_provider service unavailable")
        return SearchResponse(
            answer=f"Success with {provider}",
            sources=[],
            query=query,
            metadata=Metadata(provider=provider),
        )

    mock_engine.search.side_effect = mock_search

    client = grip.Grip(engine=mock_engine, cache=False)
    resp = client.query(
        "Test fallback",
        provider="failing_provider",
        fallback="google",
    )
    assert resp.answer == "Success with google"
    assert mock_engine.search.call_count == 2


@pytest.mark.asyncio
async def test_async_grip_real_time_streaming():
    """Verify AsyncGrip streams tokens asynchronously via generator without buffering."""
    chunks = [
        StreamChunk(event="thinking", thinking="Analyzing quantum state..."),
        StreamChunk(event="delta", delta="Quantum "),
        StreamChunk(event="delta", delta="entanglement "),
        StreamChunk(event="delta", delta="verified."),
        StreamChunk(event="done"),
    ]

    mock_engine = MagicMock()
    mock_engine.stream_search.return_value = iter(chunks)

    client = grip.AsyncGrip(engine=mock_engine, cache=False)
    received_deltas = []
    received_thinking = []

    async for chunk in client.stream("What is entanglement?", provider="google"):
        if chunk.delta:
            received_deltas.append(chunk.delta)
        if chunk.thinking:
            received_thinking.append(chunk.thinking)

    assert "".join(received_deltas) == "Quantum entanglement verified."
    assert received_thinking == ["Analyzing quantum state..."]
    await client.close()


def test_client_context_management_and_pooling():
    cfg = grip.Config(
        max_retries=2,
        retry_backoff=0.1,
        pool_connections=15,
        pool_maxsize=30,
        fallback_providers=["openai", "gemini_web"],
    )
    with grip.Grip(config=cfg) as client:
        assert client.max_retries == 2
        assert client.fallback_providers == ["openai", "gemini_web"]
        assert client.pool_connections == 15
        assert client.pool_maxsize == 30
