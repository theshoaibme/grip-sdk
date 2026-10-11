"""Interactive input session management and storage for Google AI Search.

Maintains multi-turn conversational history, Google AI Mode session thread IDs,
and provides methods for running queries within a persistent session.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Generator
from typing import Any

from ..exceptions import SessionNotFoundError
from ..types import SearchResponse, SessionDetail, SessionMessage, SessionSummary, StreamChunk


class GoogleAISession:
    """An interactive multi-turn conversation session with Google AI Search."""

    def __init__(
        self,
        session_id: str | None = None,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
        engine: Any = None,
    ) -> None:
        self.session_id = session_id or str(uuid.uuid4())
        self.title = title or f"Session {self.session_id[:8]}"
        self.thread_id: str | None = None
        self.messages: list[SessionMessage] = []
        self.created_at = time.time()
        self.updated_at = self.created_at
        self.metadata = metadata or {}
        self.engine = engine
        self._lock = threading.Lock()

    def ask(
        self,
        query: str,
        engine: Any = None,
        compiled_query: str | None = None,
    ) -> SearchResponse:
        """Send a user input query to Google AI Search within this session."""
        active_engine = engine or self.engine
        if active_engine is None:
            from .engine import GoogleAIModeEngine

            active_engine = GoogleAIModeEngine()

        with self._lock:
            # Auto-title on first turn if using default title
            if not self.messages and self.title.startswith("Session "):
                self.title = query[:48] + ("…" if len(query) > 48 else "")

            user_msg = SessionMessage(
                role="user",
                content=query,
                thread_id=self.thread_id,
            )
            self.messages.append(user_msg)

            # Perform AI search with the active thread_id if known
            engine_prompt = compiled_query or query
            response = active_engine.search(
                query=engine_prompt,
                thread_id=self.thread_id,
                session_id=self.session_id,
            )

            # Update session's thread_id if new one was returned
            if response.thread_id:
                self.thread_id = response.thread_id

            assistant_msg = SessionMessage(
                role="assistant",
                content=response.answer,
                sources=[s.to_dict() if hasattr(s, "to_dict") else s for s in response.sources],
                suggestions=response.suggestions,
                thread_id=self.thread_id,
            )
            self.messages.append(assistant_msg)
            self.updated_at = time.time()

            response.session_id = self.session_id
            return response

    def stream(
        self,
        query: str,
        engine: Any = None,
        compiled_query: str | None = None,
    ) -> Generator[dict[str, Any], None, SearchResponse]:
        """Stream an AI search response in this session."""
        active_engine = engine or self.engine
        if active_engine is None:
            from .engine import GoogleAIModeEngine

            active_engine = GoogleAIModeEngine()

        with self._lock:
            if not self.messages and self.title.startswith("Session "):
                self.title = query[:48] + ("…" if len(query) > 48 else "")

            user_msg = SessionMessage(
                role="user",
                content=query,
                thread_id=self.thread_id,
            )
            self.messages.append(user_msg)

        # Stream from engine outside the lock to permit chunk yielding
        engine_prompt = compiled_query or query
        stream_gen = active_engine.stream_search(
            query=engine_prompt,
            thread_id=self.thread_id,
            session_id=self.session_id,
        )

        final_response: SearchResponse | None = None
        for chunk in stream_gen:
            if isinstance(chunk, dict):
                if chunk.get("event") == "done" and "response" in chunk:
                    resp_data = chunk["response"]
                    final_response = SearchResponse(
                        query=query,
                        answer=resp_data.get("answer", ""),
                        sources=resp_data.get("sources", []),
                        session_id=self.session_id,
                        thread_id=resp_data.get("thread_id") or self.thread_id,
                        suggestions=resp_data.get("suggestions", []),
                        thinking=resp_data.get("thinking"),
                        cached=False,
                        provider=resp_data.get("provider", "google_ai"),
                    )
            elif isinstance(chunk, StreamChunk):
                if chunk.event == "done" and chunk.response:
                    final_response = chunk.response
            yield chunk

        with self._lock:
            if final_response:
                if final_response.thread_id:
                    self.thread_id = final_response.thread_id
                assistant_msg = SessionMessage(
                    role="assistant",
                    content=final_response.answer,
                    sources=[s.to_dict() if hasattr(s, "to_dict") else s for s in final_response.sources],
                    suggestions=final_response.suggestions,
                    thinking=final_response.thinking,
                    thread_id=self.thread_id,
                )
                self.messages.append(assistant_msg)
                self.updated_at = time.time()
                return final_response

            raise RuntimeError("Stream terminated without final response")

    def get_history(self) -> list[dict[str, Any]]:
        with self._lock:
            return [m.to_dict() for m in self.messages]

    def to_detail(self) -> SessionDetail:
        with self._lock:
            return SessionDetail(
                session_id=self.session_id,
                title=self.title,
                thread_id=self.thread_id,
                created_at=self.created_at,
                updated_at=self.updated_at,
                messages=list(self.messages),
                metadata=dict(self.metadata),
            )

    def to_dict(self) -> dict[str, Any]:
        return self.to_detail().to_dict()

    def close(self) -> None:
        """Release session resources."""
        pass


class SessionStore:
    """Thread-safe registry of active Google AI Search sessions with TTL management."""

    def __init__(self, default_ttl_sec: int = 3600) -> None:
        self.default_ttl_sec = default_ttl_sec
        self._sessions: dict[str, GoogleAISession] = {}
        self._lock = threading.Lock()

    def create(
        self,
        title: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        engine: Any = None,
    ) -> GoogleAISession:
        """Create a new session."""
        session = GoogleAISession(
            session_id=session_id,
            title=title,
            metadata=metadata,
            engine=engine,
        )
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> GoogleAISession | None:
        """Retrieve a session by ID."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            # Check expiry
            if time.time() - session.updated_at > self.default_ttl_sec:
                self._sessions.pop(session_id, None)
                return None
            return session

    def get_or_raise(self, session_id: str) -> GoogleAISession:
        """Retrieve a session or raise SessionNotFoundError."""
        session = self.get(session_id)
        if session is None:
            raise SessionNotFoundError(f"Session '{session_id}' not found or has expired.")
        return session

    def get_or_create(
        self,
        session_id: str | None = None,
        title: str | None = None,
        engine: Any = None,
    ) -> GoogleAISession:
        """Retrieve existing session or create a new one."""
        if session_id:
            existing = self.get(session_id)
            if existing is not None:
                return existing
        return self.create(title=title, session_id=session_id, engine=engine)

    def list_all(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        """List summary metadata for active sessions, sorted by newest activity."""
        self.cleanup_expired()
        with self._lock:
            sorted_sessions = sorted(
                self._sessions.values(),
                key=lambda s: s.updated_at,
                reverse=True,
            )
            paginated = sorted_sessions[offset : offset + limit]
            return [
                {
                    "session_id": s.session_id,
                    "title": s.title,
                    "thread_id": s.thread_id,
                    "message_count": len(s.messages),
                    "created_at": s.created_at,
                    "updated_at": s.updated_at,
                }
                for s in paginated
            ]

    def count(self) -> int:
        with self._lock:
            return len(self._sessions)

    def delete(self, session_id: str) -> bool:
        """Delete a session by ID."""
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is not None:
            session.close()
            return True
        return False

    def clear(self) -> int:
        """Delete all active sessions."""
        with self._lock:
            count = len(self._sessions)
            for session in self._sessions.values():
                session.close()
            self._sessions.clear()
            return count

    def cleanup_expired(self, ttl_sec: int | None = None) -> int:
        """Purge sessions inactive longer than TTL."""
        ttl = ttl_sec or self.default_ttl_sec
        now = time.time()
        expired: list[str] = []
        with self._lock:
            for sid, s in self._sessions.items():
                if now - s.updated_at > ttl:
                    expired.append(sid)
            for sid in expired:
                s = self._sessions.pop(sid, None)
                if s:
                    s.close()
        return len(expired)


# Backward-compatibility alias
SessionManager = SessionStore
