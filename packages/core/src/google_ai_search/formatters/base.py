"""Base interface for search response formatters."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from ..types.response import SearchResponse


class BaseFormatter(Protocol):
    """Protocol defining response formatting behavior."""

    def format(self, response: SearchResponse, **kwargs: Any) -> Any:
        """Format the given SearchResponse object."""
        ...
