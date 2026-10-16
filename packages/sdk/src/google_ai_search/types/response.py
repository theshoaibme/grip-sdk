"""Google AI Search response, reasoning thinking, and streaming types."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .source import SourceItem


@dataclass
class SearchResponse:
    """The complete response from a Google AI Search query, including thinking and citations."""

    query: str
    answer: str
    sources: list[SourceItem] = field(default_factory=list)
    session_id: str | None = None
    thread_id: str | None = None
    suggestions: list[str] = field(default_factory=list)
    thinking: str | None = None
    thinking_time: float | None = None
    cached: bool = False
    provider: str = "google_ai"
    search_time: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "query": self.query,
            "answer": self.answer,
            "sources": [s.to_dict() if isinstance(s, SourceItem) else s for s in self.sources],
            "cached": self.cached,
            "provider": self.provider,
        }
        if self.thinking:
            data["thinking"] = self.thinking
        if self.thinking_time is not None:
            data["thinking_time"] = round(self.thinking_time, 3)
        if self.session_id:
            data["session_id"] = self.session_id
        if self.thread_id:
            data["thread_id"] = self.thread_id
        if self.suggestions:
            data["suggestions"] = self.suggestions
        if self.search_time is not None:
            data["search_time"] = round(self.search_time, 3)
        if self.metadata:
            data["metadata"] = self.metadata
        return data

    def format(self, format_name: str = "markdown", **kwargs: Any) -> Any:
        """Format the response using one of the built-in formatters."""
        from ..formatters import format_response

        return format_response(self, format_name=format_name, **kwargs)

    def to_markdown(self, include_thinking: bool = True, include_sources: bool = True) -> str:
        """Format the response as clean GitHub-flavored markdown."""
        return self.format("markdown", include_thinking=include_thinking, include_sources=include_sources)

    def to_json(self, indent: int = 2) -> str:
        """Serialize response to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def to_citations(self, style: str = "apa") -> str:
        """Format grounded web citations into APA, BibTeX, or footnote references."""
        return self.format("citations", citation_style=style)


@dataclass
class StreamChunk:
    """A real-time token/delta chunk emitted during streaming."""

    event: str  # "delta" | "thinking" | "done" | "error"
    delta: str = ""
    text: str = ""
    thinking: str | None = None
    response: SearchResponse | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"event": self.event}
        if self.delta:
            d["delta"] = self.delta
        if self.text:
            d["text"] = self.text
        if self.thinking:
            d["thinking"] = self.thinking
        if self.response:
            d["response"] = self.response.to_dict() if hasattr(self.response, "to_dict") else self.response
        if self.error:
            d["error"] = self.error
        return d
