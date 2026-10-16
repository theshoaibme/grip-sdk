"""Response data structures for AI searches and token streaming."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from .base import DictAccessMixin
from .source import SourceItem


@dataclass
class Metadata(DictAccessMixin):
    """Search metadata metrics and timestamps."""

    search_time: float = 0.0
    cached: bool = False
    provider: str = "grip"
    timestamp: float = field(default_factory=time.time)
    request_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        search_time: float = 0.0,
        cached: bool = False,
        provider: str = "grip",
        timestamp: float | None = None,
        request_id: str | None = None,
        extra: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        latency = kwargs.pop("latency", None)
        self.search_time = latency if latency is not None else search_time
        self.cached = cached
        self.provider = provider
        self.timestamp = timestamp if timestamp is not None else time.time()
        self.request_id = request_id
        self.extra = dict(extra or {})
        if kwargs:
            self.extra.update(kwargs)

    @property
    def latency(self) -> float:
        return self.search_time

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "search_time": round(self.search_time, 3),
            "cached": self.cached,
            "provider": self.provider,
            "timestamp": self.timestamp,
            **self.extra,
        }
        if self.request_id:
            d["request_id"] = self.request_id
        return d


@dataclass
class SearchResponse(DictAccessMixin):
    """The synthesized AI search answer with grounded citations and metadata."""

    query: str
    answer: str
    sources: list[SourceItem] = field(default_factory=list)
    session_id: str | None = None
    thread_id: str | None = None
    suggestions: list[str] = field(default_factory=list)
    thinking: str | None = None
    thinking_time: float | None = None
    cached: bool = False
    provider: str = "grip"
    status: str = "success"
    search_time: float = 0.0
    timestamp: float = field(default_factory=time.time)
    request_id: str | None = None
    metadata: dict[str, Any] | Metadata = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        query: str,
        answer: str,
        sources: list[SourceItem] | None = None,
        session_id: str | None = None,
        thread_id: str | None = None,
        suggestions: list[str] | None = None,
        thinking: str | None = None,
        thinking_time: float | None = None,
        cached: bool = False,
        provider: str = "grip",
        status: str = "success",
        search_time: float = 0.0,
        timestamp: float | None = None,
        request_id: str | None = None,
        metadata: dict[str, Any] | Metadata | None = None,
        extra: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self.query = query
        self.answer = answer
        self.sources = list(sources or [])
        self.session_id = session_id
        self.thread_id = thread_id
        self.suggestions = list(suggestions or [])
        self.thinking = thinking
        self.thinking_time = thinking_time
        self.cached = cached
        self.provider = provider
        self.status = status
        self.search_time = search_time
        self.timestamp = timestamp if timestamp is not None else time.time()
        self.request_id = request_id
        self.metadata = metadata if metadata is not None else {}
        self.extra = dict(extra or {})
        if kwargs:
            self.extra.update(kwargs)

    @property
    def latency(self) -> float:
        return self.search_time

    def to_dict(self) -> dict[str, Any]:
        meta_dict = self.metadata.to_dict() if isinstance(self.metadata, Metadata) else self.metadata
        d: dict[str, Any] = {
            "query": self.query,
            "answer": self.answer,
            "sources": [s.to_dict() if hasattr(s, "to_dict") else s for s in self.sources],
            "cached": self.cached,
            "provider": self.provider,
            "status": self.status,
            "thinking": self.thinking,
            "session_id": self.session_id,
            "thread_id": self.thread_id,
            "suggestions": self.suggestions,
            "search_time": round(self.search_time, 3),
            "timestamp": self.timestamp,
            "metadata": meta_dict,
            **self.extra,
        }
        if self.request_id:
            d["request_id"] = self.request_id
        return d


    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class StreamChunk:
    """A streaming token or thought event chunk yielded during search generation."""

    event: str = "delta"  # "delta" | "thinking" | "done" | "error"
    delta: str = ""
    text: str = ""
    content: str = ""
    thinking: str | None = None
    sources: list[SourceItem] = field(default_factory=list)
    response: SearchResponse | None = None
    error: str | None = None

    def __init__(
        self,
        event: str | None = None,
        type: str | None = None,
        delta: str = "",
        text: str = "",
        content: str = "",
        thinking: str | None = None,
        sources: list[SourceItem] | None = None,
        response: SearchResponse | None = None,
        error: str | None = None,
    ) -> None:
        self.event = event or type or "delta"
        self.delta = delta
        self.text = text or delta
        self.content = content or text or delta
        self.thinking = thinking
        self.sources = sources or []
        self.response = response
        self.error = error

    @property
    def type(self) -> str:
        return self.event

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"event": self.event, "type": self.event}
        if self.delta:
            d["delta"] = self.delta
        if self.text:
            d["text"] = self.text
        if self.content:
            d["content"] = self.content
        if self.thinking:
            d["thinking"] = self.thinking
        if self.sources:
            d["sources"] = [s.to_dict() if hasattr(s, "to_dict") else s for s in self.sources]
        if self.response:
            d["response"] = self.response.to_dict() if hasattr(self.response, "to_dict") else self.response
        if self.error:
            d["error"] = self.error
        return d

    def __getitem__(self, item: str) -> Any:
        return self.to_dict()[item]

    def get(self, item: str, default: Any = None) -> Any:
        return self.to_dict().get(item, default)

    def __contains__(self, item: str) -> bool:
        return item in self.to_dict()
