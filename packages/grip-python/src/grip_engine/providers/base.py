"""Base abstract class for dynamic search AI providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generator

from grip_core.models.response import SearchResponse


class BaseSearchProvider(ABC):
    """Abstract search provider interface."""

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        """Provider identifier."""
        return self._name

    @abstractmethod
    def ready(self) -> tuple[bool, str]:
        """Verify whether provider credentials/dependencies are ready."""
        pass

    @abstractmethod
    def search(
        self,
        query: str,
        thread_id: str | None = None,
        session_id: str | None = None,
        **kwargs: Any,
    ) -> SearchResponse:
        """Execute synchronous search and answer synthesis."""
        pass

    @abstractmethod
    def stream_search(
        self,
        query: str,
        thread_id: str | None = None,
        session_id: str | None = None,
        **kwargs: Any,
    ) -> Generator[dict[str, Any], None, SearchResponse]:
        """Stream search tokens and thinking events."""
        pass
