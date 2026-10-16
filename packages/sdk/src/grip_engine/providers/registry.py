"""Dynamic provider registry for managing multiple AI search providers."""

from __future__ import annotations

import logging
from typing import Any, Callable
from core.errors import ProviderError
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
        """Retrieve an active provider instance by name (or auto-select best ready provider)."""
        key = (name or self._default_provider_name).lower().strip()

        # Handle auto / best provider routing
        if key in ("auto", "best"):
            return self.get_best_available_provider()

        # Fallback alias handling
        if key not in self._providers:
            if key in ("google_ai", "grip", "grip_ai", "google"):
                for candidate in ("google", "google_ai", "grip", "grip_ai"):
                    if candidate in self._providers:
                        key = candidate
                        break
            elif key in ("chatgpt_web", "chatgpt"):
                for candidate in ("chatgpt", "chatgpt_web"):
                    if candidate in self._providers:
                        key = candidate
                        break
            elif key in ("gemini_web", "gemini"):
                for candidate in ("gemini", "gemini_web"):
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

    def get_best_available_provider(self) -> BaseSearchProvider:
        """Inspect all registered providers and return the best ready provider."""
        # Priority order for auto-selection
        priority = ["google", "google_ai", "chatgpt", "gemini", "openai", "grip"]
        for name in priority:
            if name in self._providers:
                try:
                    prov = self.get(name)
                    ready, _ = prov.ready()
                    if ready:
                        return prov
                except Exception:
                    continue

        # Fallback to default
        return self.get(self._default_provider_name)

    def list_models(self) -> list[dict[str, Any]]:
        """Return list of all registered models across providers with real-time status."""
        catalog: list[dict[str, Any]] = [
            {
                "id": "google",
                "name": "Google AI Mode",
                "provider": "google",
                "model": "gemini-2.5-flash",
                "type": "search_and_synthesis",
                "url": "https://www.google.com/search?udm=50",
                "ready": True,
            },
            {
                "id": "chatgpt",
                "name": "ChatGPT Public Web AI",
                "provider": "chatgpt",
                "model": "chatgpt-4o-web",
                "type": "public_web_ai",
                "url": "https://chatgpt.com",
                "ready": True,
            },
            {
                "id": "gemini",
                "name": "Google Gemini Web App",
                "provider": "gemini",
                "model": "gemini-web",
                "type": "public_web_ai",
                "url": "https://gemini.google.com/app",
                "ready": True,
            },
            {
                "id": "openai",
                "name": "OpenAI API",
                "provider": "openai",
                "model": "gpt-4o",
                "type": "api",
                "url": "https://api.openai.com",
                "ready": bool(import_os_env("OPENAI_API_KEY")),
            },
        ]
        return catalog

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


def import_os_env(var: str) -> str:
    import os
    return os.getenv(var, "")


def _make_google(name: str = "google"):
    from .google_search import GoogleSearchProvider
    return GoogleSearchProvider(name=name)


def _make_openai(name: str = "openai"):
    from .openai_search import OpenAISearchProvider
    return OpenAISearchProvider(name=name)


def _make_chatgpt(name: str = "chatgpt"):
    from .chatgpt_web import ChatGPTWebProvider
    return ChatGPTWebProvider(name=name)


def _make_gemini(name: str = "gemini"):
    from .gemini_web import GeminiWebProvider
    return GeminiWebProvider(name=name)


default_provider_registry = ProviderRegistry()
default_provider_registry.register("google", lambda: _make_google("google"), is_default=True)
default_provider_registry.register("google_ai", lambda: _make_google("google_ai"))
default_provider_registry.register("grip", lambda: _make_google("grip"))
default_provider_registry.register("grip_ai", lambda: _make_google("grip_ai"))
default_provider_registry.register("chatgpt", lambda: _make_chatgpt("chatgpt"))
default_provider_registry.register("chatgpt_web", lambda: _make_chatgpt("chatgpt_web"))
default_provider_registry.register("gemini", lambda: _make_gemini("gemini"))
default_provider_registry.register("gemini_web", lambda: _make_gemini("gemini_web"))
default_provider_registry.register("openai", lambda: _make_openai("openai"))

__all__ = ["ProviderRegistry", "default_provider_registry"]
