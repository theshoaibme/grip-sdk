"""GripEngine: Core search orchestration engine with dynamic provider dispatch."""

from __future__ import annotations

from typing import Any, Generator

from google_ai_search.config import Config, get_config
from core.models.response import SearchResponse
from .infrastructure.session_store import SessionStore
from .providers.base import BaseSearchProvider
from .providers.google_search import GoogleSearchProvider
from .providers.openai_search import OpenAISearchProvider
from .providers.chatgpt_web import ChatGPTWebProvider
from .providers.gemini_web import GeminiWebProvider
from .providers.registry import ProviderRegistry


class GripEngine:
    """Core multi-provider search engine orchestration runtime."""

    def __init__(
        self,
        cfg: Config | None = None,
        default_provider: str = "google",
        registry: ProviderRegistry | None = None,
        config: Any = None,
    ) -> None:
        self.config = config or cfg or get_config()
        self.registry = registry or ProviderRegistry(default_provider_name=default_provider)
        self._default_store = SessionStore()

        # Register default providers
        self.registry.register(
            "google",
            lambda: GoogleSearchProvider(cfg=self.config, name="google"),
            is_default=(default_provider == "google"),
        )
        self.registry.register(
            "google_ai",
            lambda: GoogleSearchProvider(cfg=self.config, name="google_ai"),
        )
        self.registry.register(
            "grip",
            lambda: GoogleSearchProvider(cfg=self.config, name="grip"),
            is_default=(default_provider == "grip"),
        )
        self.registry.register(
            "grip_ai",
            lambda: GoogleSearchProvider(cfg=self.config, name="grip_ai"),
        )
        self.registry.register(
            "chatgpt",
            lambda: ChatGPTWebProvider(cfg=self.config, name="chatgpt"),
        )
        self.registry.register(
            "chatgpt_web",
            lambda: ChatGPTWebProvider(cfg=self.config, name="chatgpt_web"),
        )
        self.registry.register(
            "gemini",
            lambda: GeminiWebProvider(cfg=self.config, name="gemini"),
        )
        self.registry.register(
            "gemini_web",
            lambda: GeminiWebProvider(cfg=self.config, name="gemini_web"),
        )
        self.registry.register(
            "openai",
            lambda: OpenAISearchProvider(name="openai"),
        )

        # Agent capabilities
        from .agent.rules import RulesRegistry
        from .agent.skills import SkillsRegistry
        from .tools.builtin import ToolRegistry
        from .formatters.base import FormatterRegistry

        self.rules = RulesRegistry()
        self.skills = SkillsRegistry()
        self.tools = ToolRegistry()
        self.formatters = FormatterRegistry()
        self.workflows = None
        self.plan = None

    @property
    def name(self) -> str:
        return self.registry.default_provider_name

    @property
    def session_store(self) -> SessionStore:
        provider = self.registry.get()
        if hasattr(provider, "session_store") and provider.session_store:
            return provider.session_store
        if hasattr(provider, "_engine") and hasattr(provider._engine, "session_store") and provider._engine.session_store:
            return provider._engine.session_store
        return self._default_store

    def ready(self, provider_name: str | None = None) -> tuple[bool, str]:
        """Check status of specified or default provider."""
        provider = self.registry.get(provider_name)
        return provider.ready()

    def list_models(self) -> list[dict[str, Any]]:
        """List registered AI models and readiness status."""
        return self.registry.list_models()

    def list_providers(self) -> list[str]:
        """List all registered provider identifiers."""
        return self.registry.list_providers()

    def register_provider(
        self,
        name: str,
        provider: BaseSearchProvider,
        is_default: bool = False,
    ) -> None:
        """Dynamically add or override a search provider."""
        self.registry.register(name, provider, is_default=is_default)

    def search(
        self,
        query: str,
        thread_id: str | None = None,
        session_id: str | None = None,
        provider: str | None = None,
        **kwargs: Any,
    ) -> SearchResponse:
        """Route search query to the selected provider."""
        active_provider = self.registry.get(provider)
        return active_provider.search(
            query=query,
            thread_id=thread_id,
            session_id=session_id,
            **kwargs,
        )

    def stream_search(
        self,
        query: str,
        thread_id: str | None = None,
        session_id: str | None = None,
        provider: str | None = None,
        **kwargs: Any,
    ) -> Generator[Any, None, SearchResponse]:
        """Stream search tokens from the selected provider."""
        active_provider = self.registry.get(provider)
        return active_provider.stream_search(
            query=query,
            thread_id=thread_id,
            session_id=session_id,
            **kwargs,
        )
