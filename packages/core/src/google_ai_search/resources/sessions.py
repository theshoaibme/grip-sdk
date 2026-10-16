"""Sessions resource for managing multi-turn conversational input sessions."""

from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING, Any

from ..types import SearchResponse, SessionDetail, SessionSummary, StreamChunk

if TYPE_CHECKING:
    from ..core.engine import GoogleAIModeEngine
    from ..core.session_store import GoogleAISession, SessionStore


class SessionsResource:
    """Resource client for managing multi-turn interactive conversational sessions.

    Examples:
        >>> client = GoogleAI()
        >>> session = client.sessions.create(title="Quantum Physics")
        >>> resp1 = client.sessions.query(session.session_id, "What is superposition?")
        >>> print(resp1.answer)
        >>> resp2 = client.sessions.query(session.session_id, "How does entanglement relate to it?")
        >>> print(resp2.answer)

        # Or using session object directly:
        >>> resp3 = session.ask("What are practical applications?")
    """

    def __init__(self, engine: GoogleAIModeEngine, store: SessionStore, client: Any = None) -> None:
        self._engine = engine
        self._store = store
        self._client = client

    def create(
        self,
        title: str | None = None,
        *,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> GoogleAISession:
        """Create and register a new interactive session."""
        return self._store.create(
            title=title,
            session_id=session_id,
            metadata=metadata,
            engine=self._engine,
        )

    def retrieve(self, session_id: str) -> GoogleAISession:
        """Retrieve an existing session by ID or raise SessionNotFoundError."""
        session = self._store.get_or_raise(session_id)
        session.engine = self._engine
        return session

    def get(self, session_id: str) -> GoogleAISession | None:
        """Retrieve an existing session or return None if not found or expired."""
        session = self._store.get(session_id)
        if session:
            session.engine = self._engine
        return session

    def __getitem__(self, session_id: str) -> GoogleAISession:
        """Dictionary-like access: `client.sessions['my-session-id']`."""
        return self.retrieve(session_id)

    def list(self, limit: int = 50, offset: int = 0) -> list[SessionSummary]:
        """List active sessions as SessionSummary models."""
        summaries = self._store.list_all(limit=limit, offset=offset)
        return [
            SessionSummary(
                session_id=s["session_id"],
                title=s["title"],
                thread_id=s.get("thread_id"),
                message_count=s.get("message_count", 0),
                created_at=s.get("created_at", 0.0),
                updated_at=s.get("updated_at", 0.0),
            )
            for s in summaries
        ]

    def list_dicts(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        """List active sessions as raw dictionaries."""
        return self._store.list_all(limit=limit, offset=offset)

    def _compile_query(self, query: str) -> str:
        """Combine query with active client rules, identity, and skills if registered."""
        client = getattr(self, "_client", None)
        if not client:
            return query

        directives: list[str] = []
        if hasattr(client, "rules") and client.rules:
            rules_str = client.rules.compile()
            if rules_str:
                directives.append(rules_str)

        if hasattr(client, "skills") and client.skills:
            skills_str = client.skills.compile()
            if skills_str:
                directives.append(skills_str)

        if directives:
            return f"{query}\n\n" + "\n\n".join(directives)
        return query

    def query(self, session_id: str, query: str) -> SearchResponse:
        """Send a query into an existing session."""
        session = self.retrieve(session_id)
        compiled = self._compile_query(query)
        return session.ask(query, engine=self._engine, compiled_query=compiled if compiled != query else None)

    def ask(self, session_id: str, query: str) -> SearchResponse:
        """Alias for query()."""
        return self.query(session_id, query)

    def stream(
        self,
        session_id: str,
        query: str,
    ) -> Generator[StreamChunk, None, SearchResponse]:
        """Stream a response within an existing session."""
        session = self.retrieve(session_id)
        compiled = self._compile_query(query)
        gen = session.stream(query, engine=self._engine, compiled_query=compiled if compiled != query else None)

        final_resp: SearchResponse | None = None
        for raw in gen:
            if isinstance(raw, StreamChunk):
                if raw.event == "done" and raw.response:
                    final_resp = raw.response
                yield raw
            elif isinstance(raw, dict):
                event = raw.get("event", "delta")
                chunk = StreamChunk(
                    event=event,
                    delta=raw.get("delta", ""),
                    text=raw.get("text", ""),
                    thinking=raw.get("thinking"),
                    error=raw.get("error"),
                )
                if event == "done" and "response" in raw:
                    resp_dict = raw["response"]
                    final_resp = SearchResponse(
                        query=query,
                        answer=resp_dict.get("answer", ""),
                        sources=resp_dict.get("sources", []),
                        session_id=session_id,
                        thread_id=resp_dict.get("thread_id") or session.thread_id,
                        suggestions=resp_dict.get("suggestions", []),
                        thinking=resp_dict.get("thinking"),
                        cached=False,
                        provider=resp_dict.get("provider", "google_ai"),
                    )
                    chunk.response = final_resp
                yield chunk

        if final_resp is not None:
            return final_resp

        return SearchResponse(query=query, answer="", session_id=session_id)

    def delete(self, session_id: str) -> bool:
        """Delete an active session."""
        return self._store.delete(session_id)

    def clear(self) -> int:
        """Delete all active sessions."""
        return self._store.clear()

    def count(self) -> int:
        """Return total active sessions."""
        return self._store.count()
