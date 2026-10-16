"""Unit tests for GripEngine core orchestration."""

from unittest.mock import MagicMock
import pytest

from core.models.response import SearchResponse, SourceItem, StreamChunk
from grip_engine.engine import GripEngine
from grip_engine.providers.base import BaseSearchProvider


class DummyMockProvider(BaseSearchProvider):
    def __init__(self, name: str = "dummy"):
        super().__init__(name=name)

    def ready(self) -> tuple[bool, str]:
        return True, "Dummy is ready"

    def search(self, query: str, **kwargs) -> SearchResponse:
        return SearchResponse(
            query=query,
            answer=f"Dummy response to: {query}",
            sources=[SourceItem(title="Mock Title", url="https://example.com/mock")],
            provider=self.name,
        )

    def stream_search(self, query: str, **kwargs):
        yield StreamChunk(event="delta", delta=f"Dummy: {query}")


def test_engine_initialization():
    engine = GripEngine()
    assert "google" in engine.registry.list_providers()
    assert "openai" in engine.registry.list_providers()
    assert engine.session_store is not None
    assert engine.rules is not None


def test_engine_dynamic_provider_registration():
    engine = GripEngine()
    dummy = DummyMockProvider(name="custom_ai")
    engine.register_provider("custom_ai", dummy)

    assert "custom_ai" in engine.registry.list_providers()
    ready, reason = engine.ready("custom_ai")
    assert ready is True
    assert reason == "Dummy is ready"

    res = engine.search("Hello world", provider="custom_ai")
    assert res.answer == "Dummy response to: Hello world"
    assert res.provider == "custom_ai"
    assert len(res.sources) == 1


def test_engine_stream_search():
    engine = GripEngine()
    dummy = DummyMockProvider(name="custom_stream")
    engine.register_provider("custom_stream", dummy)

    chunks = list(engine.stream_search("stream test", provider="custom_stream"))
    assert len(chunks) == 1
    assert chunks[0].delta == "Dummy: stream test"
