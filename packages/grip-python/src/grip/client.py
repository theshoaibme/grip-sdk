"""Grip Python SDK Synchronous Client.

Enterprise AI Search, Provider Agnostic Orchestration, Agent Capabilities,
and Multi-turn Conversational Sessions.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Generator
from typing import Any

import requests

from grip_core.config import GripConfig, load_config
from grip_core.errors import GripError, ProviderError
from grip_core.models.response import Metadata, SearchResponse, StreamChunk
from grip_core.models.session import SessionDetail, SessionSummary, SessionMessage
from grip_core.models.source import SourceItem

from .config import ClientConfig
from .resources.search import SearchResource
from .resources.sessions import SessionsResource


class Grip:
    """Primary synchronous client for Grip Platform.

    Usage:
        >>> import grip
        >>> client = grip.Grip()
        >>> response = client.search.query("Quantum computing breakthroughs")
        >>> print(response.answer)

        # Or via dynamic providers
        >>> response = client.query("Latest tech news", provider="google")
        >>> response = client.query("AI agents overview", provider="openai")
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        config: GripConfig | ClientConfig | None = None,
        engine: Any = None,
        provider: str = "google",
        timeout: float = 60.0,
    ) -> None:
        self.base_url = (base_url or os.getenv("GRIP_API_URL") or "").rstrip("/")
        self.api_key = api_key or os.getenv("GRIP_API_KEY")
        self.provider = provider
        self.timeout = timeout

        if isinstance(config, GripConfig):
            self.core_config = config
        else:
            self.core_config = load_config()

        # Engine mode (if no base_url or explicitly running embedded)
        self._engine = engine
        if self._engine is None and not self.base_url:
            try:
                from grip_engine.engine import GripEngine
                self._engine = GripEngine(config=self.core_config)
            except ImportError:
                self._engine = None

        # Resources
        self.search = SearchResource(client=self)
        self.sessions = SessionsResource(client=self)

        # Agent capabilities if engine is loaded
        if self._engine is not None and hasattr(self._engine, "rules"):
            self.rules = self._engine.rules
            self.skills = self._engine.skills
            self.tools = self._engine.tools
            self.workflows = self._engine.workflows
            self.plan = self._engine.plan
            self.formatters = self._engine.formatters
        else:
            from grip_engine.agent.rules import RulesRegistry
            from grip_engine.agent.skills import SkillsRegistry
            from grip_engine.tools.builtin import ToolRegistry
            from grip_engine.formatters.base import FormatterRegistry
            self.rules = RulesRegistry()
            self.skills = SkillsRegistry()
            self.tools = ToolRegistry()
            self.formatters = FormatterRegistry()
            self.workflows = None
            self.plan = None

        # HTTP Client for remote mode
        self.api_base = self.base_url or "http://127.0.0.1:8000"
        headers = {"User-Agent": "Grip-Python-SDK/1.0.0"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        self._http = requests.Session()
        self._http.headers.update(headers)

    @property
    def engine(self) -> Any:
        return self._engine

    @property
    def session_store(self) -> Any:
        if self._engine is not None and hasattr(self._engine, "session_store"):
            return self._engine.session_store
        return None

    def ready(self, provider_name: str | None = None) -> tuple[bool, str]:
        if self._engine is not None and hasattr(self._engine, "ready"):
            return self._engine.ready(provider_name)
        return True, "Ready"

    def tool(
        self,
        name_or_fn: str | Callable[..., Any] | None = None,
        description: str | None = None,
    ) -> Any:
        """Register a custom tool decorator."""
        return self.tools.register(name_or_fn=name_or_fn, description=description)

    # -------------------------------------------------------------------------
    # Core internal execution (handles embedded or remote HTTP)
    # -------------------------------------------------------------------------

    def _url(self, path: str) -> str:
        return f"{self.api_base}{path}"

    def _execute_query(
        self,
        query: str,
        session_id: str | None = None,
        provider: str | None = None,
        thread_id: str | None = None,
        timeout: float | None = None,
    ) -> SearchResponse:
        active_provider = provider or self.provider

        # If we have an embedded engine and not strictly configured with base_url
        if self._engine is not None and not self.base_url:
            return self._engine.search(
                query=query,
                session_id=session_id,
                provider=active_provider,
                thread_id=thread_id,
            )

        # Remote API mode
        payload = {
            "query": query,
            "session_id": session_id,
            "provider": active_provider,
            "thread_id": thread_id,
        }
        res = self._http.post(self._url("/api/v1/search"), json=payload, timeout=timeout or self.timeout)
        if res.status_code >= 400:
            raise ProviderError(f"API request failed [{res.status_code}]: {res.text}")
        data = res.json()
        sources = [SourceItem(**s) for s in data.get("sources", [])]
        meta = Metadata(**data.get("metadata", {}))
        return SearchResponse(
            answer=data.get("answer", ""),
            sources=sources,
            session_id=data.get("session_id"),
            query=data.get("query", query),
            status=data.get("status", "success"),
            metadata=meta,
        )

    def _execute_stream(
        self,
        query: str,
        session_id: str | None = None,
        provider: str | None = None,
        thread_id: str | None = None,
    ) -> Generator[StreamChunk, None, SearchResponse]:
        active_provider = provider or self.provider

        if self._engine is not None and not self.base_url:
            for c in self._engine.stream_search(
                query=query,
                session_id=session_id,
                provider=active_provider,
                thread_id=thread_id,
            ):
                if isinstance(c, StreamChunk):
                    yield c
                elif isinstance(c, dict):
                    sources_raw = c.get("sources", [])
                    src_objs = [
                        SourceItem(**s) if isinstance(s, dict) else s
                        for s in sources_raw
                    ]
                    yield StreamChunk(
                        event=c.get("event") or c.get("type", "delta"),
                        delta=c.get("delta", ""),
                        content=c.get("content") or c.get("text", ""),
                        thinking=c.get("thinking"),
                        sources=src_objs,
                        response=c.get("response"),
                        error=c.get("error"),
                    )
                else:
                    yield c
            return

        # Remote API SSE stream mode
        payload = {
            "query": query,
            "session_id": session_id,
            "provider": active_provider,
            "thread_id": thread_id,
        }
        with self._http.post(self._url("/api/v1/search/stream"), json=payload, stream=True) as r:
            if r.status_code >= 400:
                raise ProviderError(f"Stream request failed [{r.status_code}]: {r.text}")

            accumulated_answer = ""
            final_sources: list[SourceItem] = []

            for line in r.iter_lines():
                if not line:
                    continue
                line_str = line.decode("utf-8") if isinstance(line, bytes) else line
                if not line_str.startswith("data: "):
                    continue
                raw_json = line_str[6:].strip()
                if not raw_json:
                    continue
                try:
                    chunk_data = json.loads(raw_json)
                    event_type = chunk_data.get("type", "delta")
                    delta = chunk_data.get("delta", "")
                    content = chunk_data.get("content", "")
                    if delta:
                        accumulated_answer += delta
                    sources_raw = chunk_data.get("sources", [])
                    if sources_raw:
                        final_sources = [SourceItem(**s) for s in sources_raw]

                    chunk = StreamChunk(
                        type=event_type,
                        delta=delta,
                        content=content,
                        sources=final_sources,
                    )
                    yield chunk
                except json.JSONDecodeError:
                    continue

        return SearchResponse(
            answer=accumulated_answer,
            sources=final_sources,
            session_id=session_id,
            query=query,
        )

    def _create_session(
        self,
        title: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionDetail:
        def _to_msg(m: Any) -> SessionMessage:
            if isinstance(m, SessionMessage):
                return m
            if isinstance(m, dict):
                return SessionMessage(**m)
            if hasattr(m, "to_dict"):
                return SessionMessage(**m.to_dict())
            return SessionMessage(role="assistant", content=str(m))

        if self._engine is not None and not self.base_url:
            sess = self._engine.session_store.create_session(
                title=title, session_id=session_id, metadata=metadata
            )
            detail = SessionDetail(
                session_id=sess.session_id,
                title=sess.title,
                created_at=sess.created_at,
                updated_at=sess.updated_at,
                messages=[_to_msg(m) for m in sess.messages],
                metadata=sess.metadata,
            )
            detail._client = self
            return detail

        payload = {"title": title, "session_id": session_id, "metadata": metadata or {}}
        res = self._http.post(self._url("/api/v1/sessions"), json=payload)
        res.raise_for_status()
        data = res.json()
        sess_dict = data["session"] if isinstance(data, dict) and "session" in data and isinstance(data["session"], dict) else data
        detail = SessionDetail(
            session_id=sess_dict.get("session_id", ""),
            title=sess_dict.get("title", ""),
            thread_id=sess_dict.get("thread_id"),
            created_at=sess_dict.get("created_at", 0.0),
            updated_at=sess_dict.get("updated_at", 0.0),
            messages=[_to_msg(m) for m in sess_dict.get("messages", [])],
            metadata=sess_dict.get("metadata", {}),
        )
        detail._client = self
        return detail

    def _get_session(self, session_id: str) -> SessionDetail | None:
        def _to_msg(m: Any) -> SessionMessage:
            if isinstance(m, SessionMessage):
                return m
            if isinstance(m, dict):
                return SessionMessage(**m)
            if hasattr(m, "to_dict"):
                return SessionMessage(**m.to_dict())
            return SessionMessage(role="assistant", content=str(m))

        if self._engine is not None and not self.base_url:
            sess = self._engine.session_store.get_session(session_id)
            if not sess:
                return None
            detail = SessionDetail(
                session_id=sess.session_id,
                title=sess.title,
                created_at=sess.created_at,
                updated_at=sess.updated_at,
                messages=[_to_msg(m) for m in sess.messages],
                metadata=sess.metadata,
            )
            detail._client = self
            return detail

        res = self._http.get(self._url(f"/api/v1/sessions/{session_id}"))
        if res.status_code == 404:
            return None
        res.raise_for_status()
        data = res.json()
        sess_dict = data["session"] if isinstance(data, dict) and "session" in data and isinstance(data["session"], dict) else data
        detail = SessionDetail(
            session_id=sess_dict.get("session_id", ""),
            title=sess_dict.get("title", ""),
            thread_id=sess_dict.get("thread_id"),
            created_at=sess_dict.get("created_at", 0.0),
            updated_at=sess_dict.get("updated_at", 0.0),
            messages=[_to_msg(m) for m in sess_dict.get("messages", [])],
            metadata=sess_dict.get("metadata", {}),
        )
        detail._client = self
        return detail

    def _list_sessions(self) -> list[SessionSummary]:
        if self._engine is not None and not self.base_url:
            items = self._engine.session_store.list_sessions()
            return [
                SessionSummary(
                    session_id=s.session_id,
                    title=s.title,
                    message_count=len(s.messages),
                    created_at=s.created_at,
                    updated_at=s.updated_at,
                )
                for s in items
            ]

        res = self._http.get(self._url("/api/v1/sessions"))
        res.raise_for_status()
        data = res.json()
        raw_list = data.get("sessions", data) if isinstance(data, dict) else data

        def _to_summary(s: Any) -> SessionSummary:
            if isinstance(s, SessionSummary):
                return s
            if isinstance(s, dict):
                return SessionSummary(
                    session_id=s.get("session_id", ""),
                    title=s.get("title", ""),
                    thread_id=s.get("thread_id"),
                    message_count=s.get("message_count", 0),
                    created_at=s.get("created_at", 0.0),
                    updated_at=s.get("updated_at", 0.0),
                )
            return s

        return [
            _to_summary(s)
            for s in (raw_list if isinstance(raw_list, list) else [])
        ]


    def _delete_session(self, session_id: str) -> bool:
        if self._engine is not None and not self.base_url:
            return self._engine.session_store.delete_session(session_id)

        res = self._http.delete(self._url(f"/api/v1/sessions/{session_id}"))
        return res.status_code == 200

    def _clear_sessions(self) -> int:
        if self._engine is not None and not self.base_url:
            return self._engine.session_store.clear_all()

        res = self._http.post(self._url("/api/v1/sessions/clear"))
        return res.json().get("cleared", 0)

    # -------------------------------------------------------------------------
    # Top-level Ergonomic Shortcuts
    # -------------------------------------------------------------------------

    def query(
        self,
        query: str,
        session_id: str | None = None,
        provider: str | None = None,
        timeout: float | None = None,
    ) -> SearchResponse:
        """Top-level shorthand for query."""
        return self.search.query(
            query=query, session_id=session_id, provider=provider, timeout=timeout
        )

    def stream(
        self,
        query: str,
        session_id: str | None = None,
        provider: str | None = None,
    ) -> Generator[StreamChunk, None, SearchResponse]:
        """Top-level shorthand for streaming."""
        return self.search.stream(query=query, session_id=session_id, provider=provider)

    def chat(
        self,
        query: str,
        session_id: str | None = None,
        title: str | None = None,
        provider: str | None = None,
    ) -> SearchResponse:
        """Convenient multi-turn chat wrapper."""
        if not session_id:
            sess = self.sessions.create(title=title or "Chat Session")
            session_id = sess.session_id
        return self.sessions.query(session_id=session_id, query=query, provider=provider)

    def create_session(
        self,
        title: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionDetail:
        return self.sessions.create(title=title, session_id=session_id, metadata=metadata)

    def get_session(self, session_id: str) -> SessionDetail | None:
        return self.sessions.get(session_id=session_id)

    def list_sessions(self) -> list[SessionSummary]:
        return self.sessions.list()

    def delete_session(self, session_id: str) -> bool:
        return self.sessions.delete(session_id=session_id)

    def create_agent(
        self,
        name: str = "GripAgent",
        provider: str = "google",
        model: str | None = None,
        instructions: str | None = None,
        tools: list[Any] | None = None,
        mcp_clients: list[Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Create an autonomous AI Agent with model based on provider, tools, PDF creation, and MCP support."""
        from .agent import Agent
        return Agent(
            name=name,
            provider=provider,
            model=model,
            instructions=instructions,
            client=self,
            tools=tools,
            mcp_clients=mcp_clients,
            **kwargs,
        )

    def agent(
        self,
        provider: str = "google",
        model: str | None = None,
        instructions: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Shorthand to create an autonomous AI Agent."""
        return self.create_agent(
            provider=provider,
            model=model,
            instructions=instructions,
            **kwargs,
        )

    def clear_sessions(self) -> int:
        return self.sessions.clear()

    def close(self) -> None:
        """Close underlying HTTP connections."""
        self._http.close()

    def __enter__(self) -> Grip:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()


Client = Grip
GripClient = Grip
