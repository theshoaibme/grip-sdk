"""Search resource for executing AI queries and real-time streams."""

from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING, Any

from ..types import SearchResponse, StreamChunk

if TYPE_CHECKING:
    from ..client import GoogleAI
    from ..core.engine import GoogleAIModeEngine
    from ..core.session_store import SessionStore


class SearchResource:
    """Resource client for performing Google AI searches and token streaming.

    Examples:
        >>> client = GoogleAI()
        >>> response = client.search.query("Latest breakthrough in fusion energy")
        >>> print(response.answer)
        >>> for source in response.sources:
        ...     print(source.title, source.link)

        # Direct callable convenience:
        >>> response = client.search("What is gravity?")

        # Real-time streaming:
        >>> for chunk in client.search.stream("Explain relativity"):
        ...     if chunk.event == "delta":
        ...         print(chunk.delta, end="", flush=True)
    """

    def __init__(
        self,
        engine: GoogleAIModeEngine,
        sessions: SessionStore | None = None,
        client: GoogleAI | None = None,
    ) -> None:
        self._engine = engine
        self._sessions = sessions
        self._client = client

    def __call__(
        self,
        query: str,
        *,
        session_id: str | None = None,
        thread_id: str | None = None,
    ) -> SearchResponse:
        """Shorthand callable: `client.search("query")` delegates to `query()`."""
        return self.query(query, session_id=session_id, thread_id=thread_id)

    def _compile_query(self, query: str) -> str:
        """Combine query with active client rules and skills if registered."""
        if not self._client:
            return query

        directives: list[str] = []
        if hasattr(self._client, "rules") and self._client.rules:
            rules_str = self._client.rules.compile()
            if rules_str:
                directives.append(rules_str)

        if hasattr(self._client, "skills") and self._client.skills:
            skills_str = self._client.skills.compile()
            if skills_str:
                directives.append(skills_str)

        if directives:
            return f"{query}\n\n" + "\n\n".join(directives)
        return query

    def query(
        self,
        query: str,
        *,
        session_id: str | None = None,
        thread_id: str | None = None,
        timeout: float | None = None,
    ) -> SearchResponse:
        """Execute a Google AI Search in browser mode.

        Args:
            query: The search prompt or question.
            session_id: Optional session identifier to maintain conversation history.
            thread_id: Optional Google AI Mode internal thread ID for continuity.
            timeout: Optional search timeout override in seconds.

        Returns:
            A SearchResponse object containing the synthesized answer and grounded sources.
        """
        effective_query = self._compile_query(query)

        if session_id and self._sessions:
            session = self._sessions.get_or_create(session_id=session_id, engine=self._engine)
            return session.ask(effective_query, engine=self._engine)

        return self._engine.search(query=effective_query, thread_id=thread_id)

    def stream(
        self,
        query: str,
        *,
        session_id: str | None = None,
        thread_id: str | None = None,
        timeout: float | None = None,
    ) -> Generator[StreamChunk, None, SearchResponse]:
        """Stream Google AI Search response tokens in real-time.

        Args:
            query: The search prompt or question.
            session_id: Optional session identifier to maintain conversation history.
            thread_id: Optional Google AI Mode thread ID.

        Yields:
            StreamChunk objects with events: "thinking", "delta", "done", or "error".
        """
        effective_query = self._compile_query(query)

        if session_id and self._sessions:
            session = self._sessions.get_or_create(session_id=session_id, engine=self._engine)
            gen = session.stream(effective_query, engine=self._engine)
        else:
            gen = self._engine.stream_search(query=effective_query, thread_id=thread_id)

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
                    thinking=raw.get("thinking", ""),
                    error=raw.get("error"),
                )
                if event == "done" and "response" in raw:
                    resp_dict = raw["response"]
                    final_resp = SearchResponse(
                        query=query,
                        answer=resp_dict.get("answer", ""),
                        sources=resp_dict.get("sources", []),
                        session_id=session_id,
                        thread_id=resp_dict.get("thread_id") or thread_id,
                        suggestions=resp_dict.get("suggestions", []),
                        thinking=resp_dict.get("thinking"),
                        cached=False,
                        provider=resp_dict.get("provider", "google_ai"),
                    )
                    chunk.response = final_resp
                yield chunk

        if final_resp is not None:
            return final_resp

        return SearchResponse(query=query, answer="")
