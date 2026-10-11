"""Dynamic provider registry for managing multiple AI search providers."""

from __future__ import annotations

import logging
from typing import Any, Callable
from grip_core.errors import ProviderError
from .base import BaseSearchProvider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Registry maintaining dynamic search providers (Google, OpenAI, Bing, Perplexity, etc.)."""

    def __init__(self, default_provider_name: str = "google") -> None:
        self._providers: dict[str, BaseSearchProvider | Callable[[], BaseSearchProvider]] = {}
        self._default_provider_name = default_provider_name

    def register(
        self,
        name: str,
        provider: BaseSearchProvider | Callable[[], BaseSearchProvider],
        is_default: bool = False,
    ) -> None:
        """Register a search provider dynamically."""
        key = name.lower().strip()
        self._providers[key] = provider
        if is_default:
            self._default_provider_name = key
        logger.info("Registered search provider '%s' (default=%s)", key, is_default)

    def get(self, name: str | None = None) -> BaseSearchProvider:
        """Retrieve an active provider instance by name (or default)."""
        key = (name or self._default_provider_name).lower().strip()
        if key not in self._providers:
            # Fallback alias handling
            if key in ("google_ai", "grip", "grip_ai", "google"):
                for candidate in ("google", "google_ai", "grip", "grip_ai"):
                    if candidate in self._providers:
                        key = candidate
                        break

        if key not in self._providers:
            available = ", ".join(self._providers.keys())
            raise ProviderError(f"Unknown search provider '{name}'. Available providers: {available}")

        entry = self._providers[key]
        if callable(entry) and not isinstance(entry, BaseSearchProvider):
            instance = entry()
            self._providers[key] = instance
            return instance
        return entry

    def list_providers(self) -> list[str]:
        """List all registered provider names."""
        return list(self._providers.keys())

    @property
    def default_provider_name(self) -> str:
        return self._default_provider_name

    def set_default(self, name: str) -> None:
        key = name.lower().strip()
        if key not in self._providers:
            raise ValueError(f"Cannot set unknown provider '{name}' as default.")
        self._default_provider_name = key


def _make_google(name: str = "google"):
    from .google_search import GoogleSearchProvider
    return GoogleSearchProvider(name=name)


def _make_openai(name: str = "openai"):
    from .openai_search import OpenAISearchProvider
    return OpenAISearchProvider(name=name)


default_provider_registry = ProviderRegistry()
default_provider_registry.register("google", lambda: _make_google("google"), is_default=True)
default_provider_registry.register("google_ai", lambda: _make_google("google_ai"))
default_provider_registry.register("grip", lambda: _make_google("grip"))
default_provider_registry.register("grip_ai", lambda: _make_google("grip_ai"))
default_provider_registry.register("openai", lambda: _make_openai("openai"))

__all__ = ["ProviderRegistry", "default_provider_registry"]
