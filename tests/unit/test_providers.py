"""Unit tests for Search Providers and ProviderRegistry."""

import pytest

from grip_core.errors import ProviderError
from grip_engine.providers.base import BaseSearchProvider
from grip_engine.providers.openai_search import OpenAISearchProvider
from grip_engine.providers.registry import ProviderRegistry


class MockProvider(BaseSearchProvider):
    def ready(self) -> tuple[bool, str]:
        return True, "Ready"

    def search(self, query: str, **kwargs):
        pass

    def stream_search(self, query: str, **kwargs):
        pass


def test_provider_registry_register_and_get():
    registry = ProviderRegistry(default_provider_name="p1")
    p1 = MockProvider(name="p1")
    registry.register("p1", p1, is_default=True)

    assert registry.get("p1") is p1
    assert registry.get() is p1
    assert "p1" in registry.list_providers()


def test_provider_registry_missing_provider_raises():
    registry = ProviderRegistry()
    with pytest.raises(ProviderError):
        registry.get("nonexistent_provider")


def test_openai_search_provider_requires_key_or_reports_status():
    provider = OpenAISearchProvider(api_key="test-key")
    ready, reason = provider.ready()
    assert ready is True
    assert "ready" in reason.lower()

    unconfigured = OpenAISearchProvider(api_key=None)
    # If no env var set
    import os
    if not os.getenv("OPENAI_API_KEY"):
        ready, reason = unconfigured.ready()
        assert ready is False
        assert "OPENAI_API_KEY" in reason
