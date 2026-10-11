"""Request data transfer models for Grip Platform."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SearchRequest:
    """Incoming request model for AI Search queries."""

    query: str
    session_id: str | None = None
    thread_id: str | None = None
    provider: str | None = None
    stream: bool = False
    timeout: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionCreateRequest:
    """Request model for creating a conversational session."""

    title: str | None = None
    initial_query: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
