"""Interactive session models and message histories."""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SessionMessage:
    """A single turn (user prompt or AI response) inside a session."""

    role: str  # "user" | "assistant"
    content: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sources: list[dict[str, str]] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    thinking: str | None = None
    timestamp: float = field(default_factory=time.time)
    thread_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "sources": self.sources,
            "suggestions": self.suggestions,
            "thinking": self.thinking,
            "timestamp": self.timestamp,
            "thread_id": self.thread_id,
        }


@dataclass
class SessionSummary:
    """Compact summary of an active session."""

    session_id: str
    title: str
    thread_id: str | None = None
    message_count: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "thread_id": self.thread_id,
            "message_count": self.message_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class SessionDetail:
    """Detailed session object with complete multi-turn conversation messages."""

    session_id: str
    title: str
    thread_id: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    messages: list[SessionMessage] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "thread_id": self.thread_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message_count": len(self.messages),
            "messages": [m.to_dict() if hasattr(m, "to_dict") else m for m in self.messages],
            "metadata": self.metadata,
        }
