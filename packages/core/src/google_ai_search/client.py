"""Modern SDK Client for Google AI Search.

Provides programmatic access to Google AI Search in browser mode with real-time
streaming, grounded citations, multi-turn conversational session management,
skills, rules, strict planning, workflow pipelines, and built-in tools.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from types import TracebackType
from typing import Any

from .agent import PlanManager, RulesRegistry, SkillsRegistry, WorkflowManager
from .config import Config, get_config
from .core.engine import GoogleAIModeEngine
from .core.session_store import GoogleAISession, SessionStore
from .formatters import FormatterRegistry
from .resources.search import SearchResource
from .resources.sessions import SessionsResource
from .tools import ToolRegistry
from .types import SearchResponse, SessionSummary, StreamChunk


class GoogleAI:
    """Primary SDK Client for Google AI Search.

    Modern resource-based architecture:
        - `client.search`: Search resource (`query`, `stream`, or direct call `client.search(...)`)
        - `client.sessions`: Interactive multi-turn sessions resource (`create`, `retrieve`, `query`, `stream`, `list`, `delete`)
        - `client.rules`: Behavioral, formatting, and negative constraints registry
        - `client.skills`: Domain capabilities and instruction sets registry
        - `client.tools`: Built-in and user-registered callable tools registry
        - `client.workflows`: Automated execution pipelines (`client.workflows.create(...)`)
        - `client.plan`: Goal-oriented strict execution planner (`client.plan.create(...)`)
        - `client.formatters`: Response formatting engine (markdown, JSON, APA, BibTeX, HTML)

    Examples:
        >>> from google_ai_search import GoogleAI
        >>> client = GoogleAI()

        # One-shot search
        >>> response = client.search.query("Latest fusion energy milestones")
        >>> print(response.answer)
        >>> print(response.to_markdown())

        # Rules
        >>> client.rules.add("Always cite primary scientific sources")
        >>> client.rules.add("Output in bullet points")

        # Built-in Tools
        >>> res = client.tools.call("calculator", expression="45 * 12 + 10")
        >>> print(res)

        # Strict Plan
        >>> plan = client.plan.create("Research Quantum", ["Search qubits", "Verify sources"])
        >>> result = plan.execute(client)
    """

    def __init__(
        self,
        config: Config | None = None,
        session_ttl_sec: int | None = None,
        *,
        engine: GoogleAIModeEngine | None = None,
        session_store: SessionStore | None = None,
    ) -> None:
        self.config = config or get_config()
        self._engine = engine or GoogleAIModeEngine(self.config)

        ttl = session_ttl_sec or self.config.session_ttl_sec
        self._session_store = session_store or SessionStore(default_ttl_sec=ttl)

        # Resource namespaces
        self.search = SearchResource(engine=self._engine, sessions=self._session_store, client=self)
        self.sessions = SessionsResource(engine=self._engine, store=self._session_store, client=self)

        # Agentic capabilities
        self.rules = RulesRegistry()
        self.skills = SkillsRegistry()
        self.tools = ToolRegistry(load_builtins=True)
        self.workflows = WorkflowManager(self)
        self.plan = PlanManager(self)
        self.formatters = FormatterRegistry()

    @property
    def engine(self) -> GoogleAIModeEngine:
        """The underlying browser automation engine."""
        return self._engine

    @engine.setter
    def engine(self, value: GoogleAIModeEngine) -> None:
        self._engine = value
        self.search._engine = value
        self.sessions._engine = value

    @property
    def session_store(self) -> SessionStore:
        """Underlying session persistence store."""
        return self._session_store

    def tool(
        self,
        name_or_fn: str | Callable[..., Any] | None = None,
        description: str | None = None,
    ) -> Any:
        """Decorator shortcut to register a custom tool with the client.

        Usage:
            @client.tool(description="Calculate growth rate")
            def growth_rate(start: float, end: float) -> float:
                return (end - start) / start
        """
        return self.tools.register(name_or_fn=name_or_fn, description=description)

    # -------------------------------------------------------------------------
    # Ergonomic top-level shortcuts
    # -------------------------------------------------------------------------

    def query(
        self,
        query: str,
        session_id: str | None = None,
        thread_id: str | None = None,
    ) -> SearchResponse:
        """Execute a search query (shortcut for `client.search.query`)."""
        return self.search.query(query, session_id=session_id, thread_id=thread_id)

    def stream(
        self,
        query: str,
        session_id: str | None = None,
        thread_id: str | None = None,
    ) -> Generator[StreamChunk, None, SearchResponse]:
        """Stream a search response in real-time (shortcut for `client.search.stream`)."""
        return self.search.stream(query, session_id=session_id, thread_id=thread_id)

    def stream_search(
        self,
        query: str,
        session_id: str | None = None,
        thread_id: str | None = None,
    ) -> Generator[StreamChunk, None, SearchResponse]:
        """Alias for stream()."""
        return self.stream(query, session_id=session_id, thread_id=thread_id)

    def create_session(
        self,
        title: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> GoogleAISession:
        """Create a new conversational input session."""
        return self.sessions.create(
            title=title,
            session_id=session_id,
            metadata=metadata,
        )

    def get_session(self, session_id: str) -> GoogleAISession | None:
        """Retrieve an active session by ID, or None if not found."""
        return self.sessions.get(session_id)

    def list_sessions(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        """List active sessions as metadata dicts."""
        return self.sessions.list_dicts(limit=limit, offset=offset)

    def delete_session(self, session_id: str) -> bool:
        """Delete an active session."""
        return self.sessions.delete(session_id)

    def clear_sessions(self) -> int:
        """Clear all active sessions."""
        return self.sessions.clear()

    def ready(self) -> tuple[bool, str]:
        """Check if client and underlying engine are ready."""
        return self._engine.ready()

    def close(self) -> None:
        """Release any client resources."""
        self._session_store.clear()

    def __enter__(self) -> GoogleAI:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()


# Backward compatibility aliases
GoogleAISearch = GoogleAI
GoogleAISearchClient = GoogleAI
