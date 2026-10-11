"""Extensible interface protocols for dynamic search providers, agents, and formatters."""

from __future__ import annotations

from typing import Any, Generator, Protocol, runtime_checkable
from .models.response import SearchResponse, StreamChunk


@runtime_checkable
class SearchProviderProtocol(Protocol):
    """Protocol for dynamic search engines (Google, OpenAI, Perplexity, etc.)."""

    @property
    def name(self) -> str:
        """Unique provider identifier (e.g. 'google', 'openai', 'perplexity')."""
        ...

    def ready(self) -> tuple[bool, str]:
        """Check if provider dependencies, environment keys, and browsers are ready."""
        ...

    def search(
        self,
        query: str,
        thread_id: str | None = None,
        session_id: str | None = None,
        **kwargs: Any,
    ) -> SearchResponse:
        """Execute a synchronous search and synthesis."""
        ...

    def stream_search(
        self,
        query: str,
        thread_id: str | None = None,
        session_id: str | None = None,
        **kwargs: Any,
    ) -> Generator[dict[str, Any], None, SearchResponse]:
        """Stream search tokens and thoughts in real time."""
        ...


@runtime_checkable
class FormatterProtocol(Protocol):
    """Protocol for response formatters (Markdown, JSON, HTML, Citations)."""

    def format(self, response: SearchResponse) -> str:
        ...


@runtime_checkable
class SessionStoreProtocol(Protocol):
    """Protocol for session registry and storage."""

    def get(self, session_id: str) -> Any:
        ...

    def create(self, title: str | None = None, **kwargs: Any) -> Any:
        ...
