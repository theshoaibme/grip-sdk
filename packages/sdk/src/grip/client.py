"""Grip Python SDK Synchronous Client.

Enterprise AI Search, Provider Agnostic Orchestration, Agent Capabilities,
and Multi-turn Conversational Sessions.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from collections.abc import Callable, Generator
from typing import Any

import requests
from urllib3.util import Retry
from requests.adapters import HTTPAdapter

from core.config import GripConfig, load_config
from core.errors import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BotBlockedError,
    GripError,
    NotFoundError,
    ProviderError,
    QuotaExceededError,
    RateLimitError,
    SessionNotFoundError,
    ValidationError,
)
from core.models.response import Metadata, SearchResponse, StreamChunk
from core.models.session import SessionDetail, SessionSummary, SessionMessage
from core.models.source import SourceItem

from ._version import __version__
from .config import ClientConfig
from .resources.search import SearchResource
from .resources.sessions import SessionsResource

logger = logging.getLogger("grip")


class Grip:
    """Primary synchronous client for Grip Platform.

    Enterprise-grade AI Search, Multi-Provider Orchestration, Agent Capabilities,
    and Conversational Sessions with built-in retries, connection pooling, and fallback.

    Usage:
        >>> import grip
        >>> client = grip.Grip()
        >>> response = client.search.query("Quantum computing breakthroughs")
        >>> print(response.answer)

        # Or via dynamic providers with fallback
        >>> response = client.query("Latest tech news", provider="chatgpt_web", fallback="google")
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        config: GripConfig | ClientConfig | None = None,
        engine: Any = None,
        provider: str = "google",
        timeout: float | tuple[float, float] = 60.0,
        user_agent: str | None = None,
        use_system_profile: bool = False,
        chrome_profile_dir: str | None = None,
        cache: bool = True,
        cache_ttl: int = 3600,
        low_latency: bool = True,
        max_retries: int | None = None,
        retry_backoff: float | None = None,
        pool_connections: int | None = None,
        pool_maxsize: int | None = None,
        fallback_providers: list[str] | None = None,
    ) -> None:
        resolved_cfg: ClientConfig | None = None
        if isinstance(config, ClientConfig):
            resolved_cfg = config
            self.core_config = load_config()
        elif isinstance(config, GripConfig):
            self.core_config = config
        else:
            self.core_config = load_config()

        self.base_url = (
            base_url
            or os.getenv("GRIP_API_URL")
            or (resolved_cfg.api_base_url if resolved_cfg else None)
            or ""
        ).rstrip("/")
        self.api_key = api_key or os.getenv("GRIP_API_KEY") or (resolved_cfg.api_key if resolved_cfg else None)
        self.provider = (
            provider
            if provider != "google" or not resolved_cfg
            else (resolved_cfg.default_provider or "google")
        )
        self.timeout = timeout if timeout != 60.0 or not resolved_cfg else resolved_cfg.timeout
        self.user_agent = (
            user_agent
            or os.getenv("USER_AGENT_OVERRIDE")
            or os.getenv("GRIP_USER_AGENT")
            or (resolved_cfg.user_agent if resolved_cfg else None)
        )
        self.cache_enabled = (
            cache
            if resolved_cfg is None
            else resolved_cfg.cache_enabled
        )
        self.low_latency = low_latency

        self.max_retries = (
            max_retries
            if max_retries is not None
            else (resolved_cfg.max_retries if resolved_cfg else int(os.getenv("GRIP_MAX_RETRIES", "3")))
        )
        self.retry_backoff = (
            retry_backoff
            if retry_backoff is not None
            else (resolved_cfg.retry_backoff if resolved_cfg else float(os.getenv("GRIP_RETRY_BACKOFF", "0.5")))
        )
        self.pool_connections = (
            pool_connections
            if pool_connections is not None
            else (resolved_cfg.pool_connections if resolved_cfg else int(os.getenv("GRIP_POOL_CONNECTIONS", "25")))
        )
        self.pool_maxsize = (
            pool_maxsize
            if pool_maxsize is not None
            else (resolved_cfg.pool_maxsize if resolved_cfg else int(os.getenv("GRIP_POOL_MAXSIZE", "50")))
        )

        if fallback_providers is not None:
            self.fallback_providers = list(fallback_providers)
        elif resolved_cfg and resolved_cfg.fallback_providers:
            self.fallback_providers = list(resolved_cfg.fallback_providers)
        else:
            fallbacks_env = os.getenv("GRIP_FALLBACK_PROVIDERS", "")
            self.fallback_providers = [p.strip() for p in fallbacks_env.split(",") if p.strip()]

        from grip_engine.infrastructure.cache import TTLCache
        effective_ttl = cache_ttl if not resolved_cfg else resolved_cfg.cache_ttl
        self._cache: TTLCache | None = TTLCache(ttl=effective_ttl, max_entries=1000) if self.cache_enabled else None

        if use_system_profile:
            setattr(self.core_config, "browser_use_system_profile", True)
        if chrome_profile_dir:
            setattr(self.core_config, "browser_user_data_dir", chrome_profile_dir)
        if self.user_agent:
            setattr(self.core_config, "user_agent_override", self.user_agent)

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

        # HTTP Client for remote mode with enterprise pooling and retries
        self.api_base = self.base_url or "http://127.0.0.1:8000"
        headers = {
            "User-Agent": f"Grip-Python-SDK/{__version__}",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        self._http = requests.Session()
        self._http.headers.update(headers)

        if self.max_retries > 0:
            retry_strategy = Retry(
                total=self.max_retries,
                backoff_factor=self.retry_backoff,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET", "POST", "DELETE", "PUT", "HEAD"],
                raise_on_status=False,
            )
        else:
            retry_strategy = False

        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=self.pool_connections,
            pool_maxsize=self.pool_maxsize,
        )
        self._http.mount("https://", adapter)
        self._http.mount("http://", adapter)


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

    def warmup(self) -> None:
        """Pre-warm engine and session components to minimize query latency."""
        if self._engine is not None and hasattr(self._engine, "warmup"):
            self._engine.warmup()

    def list_models(self) -> list[dict[str, Any]]:
        """List registered AI models and readiness status."""
        if self._engine is not None and hasattr(self._engine, "list_models"):
            return self._engine.list_models()
        try:
            res = self._http.get(self._url("/api/v1/models"), timeout=self.timeout)
            if res.status_code == 200:
                return res.json().get("models", [])
        except Exception:
            pass
        from grip_engine.providers.registry import default_provider_registry
        return default_provider_registry.list_models()

    def list_providers(self) -> list[str]:
        """List all available provider names."""
        if self._engine is not None and hasattr(self._engine, "list_providers"):
            return self._engine.list_providers()
        from grip_engine.providers.registry import default_provider_registry
        return default_provider_registry.list_providers()

    def _handle_response_error(self, res: requests.Response) -> None:
        status_code = res.status_code
        req_id = res.headers.get("X-Request-ID")
        try:
            body = res.json()
            message = (
                body.get("error", {}).get("message")
                if isinstance(body.get("error"), dict)
                else (body.get("detail") or body.get("message") or res.text)
            )
        except Exception:
            body = res.text
            message = res.text or f"HTTP Error {status_code}"

        if status_code in (401, 403):
            raise AuthenticationError(f"Authentication failed [{status_code}]: {message}")
        if status_code == 404:
            raise NotFoundError(f"Resource not found [{status_code}]: {message}")
        if status_code == 429:
            raise RateLimitError(f"Rate limit exceeded [{status_code}]: {message}")
        raise APIStatusError(
            f"API request failed [{status_code}]: {message}",
            status_code=status_code,
            body=body,
            request_id=req_id,
        )

    def _execute_query(
        self,
        query: str,
        session_id: str | None = None,
        provider: str | None = None,
        thread_id: str | None = None,
        timeout: float | tuple[float, float] | None = None,
        user_agent: str | None = None,
        fallback: str | list[str] | None = None,
    ) -> SearchResponse:
        active_provider = provider or self.provider
        effective_ua = user_agent or self.user_agent

        providers_to_try = [active_provider]
        if fallback:
            fb_list = [fallback] if isinstance(fallback, str) else list(fallback)
            for fb in fb_list:
                if fb not in providers_to_try:
                    providers_to_try.append(fb)
        elif self.fallback_providers:
            for fb in self.fallback_providers:
                if fb not in providers_to_try:
                    providers_to_try.append(fb)

        last_err: Exception | None = None
        for prov in providers_to_try:
            try:
                # Ultra-low latency cache check (< 1ms)
                cache_key = f"{prov}:{query.strip().lower()}:{thread_id or ''}"
                if self.cache_enabled and self._cache is not None:
                    cached_res = self._cache.get(cache_key)
                    if cached_res is not None:
                        import dataclasses
                        if dataclasses.is_dataclass(cached_res):
                            return dataclasses.replace(cached_res, cached=True, search_time=0.0002)
                        if hasattr(cached_res, "model_copy"):
                            return cached_res.model_copy(update={"cached": True, "search_time": 0.0002})
                        return cached_res

                # If we have an embedded engine and not strictly configured with base_url
                if self._engine is not None and not self.base_url:
                    res = self._engine.search(
                        query=query,
                        session_id=session_id,
                        provider=prov,
                        thread_id=thread_id,
                        user_agent=effective_ua,
                    )
                    if self.cache_enabled and self._cache is not None:
                        self._cache.set(cache_key, res)
                    return res

                # Remote API mode
                payload = {
                    "query": query,
                    "session_id": session_id,
                    "provider": prov,
                    "thread_id": thread_id,
                }
                req_headers = {"X-Request-ID": f"req_{uuid.uuid4().hex[:12]}"}
                if effective_ua:
                    req_headers["User-Agent"] = effective_ua

                try:
                    res = self._http.post(
                        self._url("/api/v1/search"),
                        json=payload,
                        headers=req_headers,
                        timeout=timeout or self.timeout,
                    )
                except requests.exceptions.Timeout as te:
                    raise APITimeoutError(f"Search request timed out: {te}") from te
                except requests.exceptions.ConnectionError as ce:
                    raise APIConnectionError(f"Connection failed: {ce}") from ce

                if res.status_code >= 400:
                    self._handle_response_error(res)

                data = res.json()
                sources = [SourceItem(**s) for s in data.get("sources", [])]
                meta_dict = data.get("metadata", {})
                if "request_id" not in meta_dict and "X-Request-ID" in res.headers:
                    meta_dict["request_id"] = res.headers["X-Request-ID"]
                meta = Metadata(**meta_dict)
                resp = SearchResponse(
                    answer=data.get("answer", ""),
                    sources=sources,
                    session_id=data.get("session_id"),
                    query=data.get("query", query),
                    status=data.get("status", "success"),
                    metadata=meta,
                )
                if self.cache_enabled and self._cache is not None:
                    self._cache.set(cache_key, resp)
                return resp
            except Exception as e:
                last_err = e
                logger.warning("Provider '%s' failed: %s", prov, e)
                if prov != providers_to_try[-1]:
                    continue
                raise

        if last_err:
            raise last_err
        raise ProviderError(f"All providers failed: {providers_to_try}")

    def _execute_stream(
        self,
        query: str,
        session_id: str | None = None,
        provider: str | None = None,
        thread_id: str | None = None,
        user_agent: str | None = None,
        fallback: str | list[str] | None = None,
    ) -> Generator[StreamChunk, None, SearchResponse]:
        active_provider = provider or self.provider
        effective_ua = user_agent or self.user_agent

        providers_to_try = [active_provider]
        if fallback:
            fb_list = [fallback] if isinstance(fallback, str) else list(fallback)
            for fb in fb_list:
                if fb not in providers_to_try:
                    providers_to_try.append(fb)
        elif self.fallback_providers:
            for fb in self.fallback_providers:
                if fb not in providers_to_try:
                    providers_to_try.append(fb)

        last_err: Exception | None = None
        for prov in providers_to_try:
            try:
                # Ultra-low latency stream cache check
                cache_key = f"{prov}:{query.strip().lower()}:{thread_id or ''}"
                if self.cache_enabled and self._cache is not None:
                    cached_res = self._cache.get(cache_key)
                    if cached_res is not None:
                        yield StreamChunk(event="thinking", thinking="Instant cached streaming response (<1ms)...")
                        words = cached_res.answer.split(" ")
                        for i, w in enumerate(words):
                            token = w + (" " if i < len(words) - 1 else "")
                            yield StreamChunk(event="delta", delta=token, content=cached_res.answer)
                        yield StreamChunk(event="done", response=cached_res.to_dict())
                        return cached_res

                if self._engine is not None and not self.base_url:
                    accumulated = ""
                    final_sources: list[SourceItem] = []
                    for c in self._engine.stream_search(
                        query=query,
                        session_id=session_id,
                        provider=prov,
                        thread_id=thread_id,
                        user_agent=effective_ua,
                    ):
                        if isinstance(c, StreamChunk):
                            if c.delta:
                                accumulated += c.delta
                            if c.sources:
                                final_sources = c.sources
                            yield c
                        elif isinstance(c, dict):
                            sources_raw = c.get("sources", [])
                            src_objs = [
                                SourceItem(**s) if isinstance(s, dict) else s
                                for s in sources_raw
                            ]
                            delta = c.get("delta", "")
                            if delta:
                                accumulated += delta
                            if src_objs:
                                final_sources = src_objs
                            yield StreamChunk(
                                event=c.get("event") or c.get("type", "delta"),
                                delta=delta,
                                content=c.get("content") or c.get("text", ""),
                                thinking=c.get("thinking"),
                                sources=src_objs,
                                response=c.get("response"),
                                error=c.get("error"),
                            )
                        else:
                            yield c
                    return SearchResponse(
                        answer=accumulated,
                        sources=final_sources,
                        session_id=session_id,
                        query=query,
                    )

                # Remote API SSE stream mode
                payload = {
                    "query": query,
                    "session_id": session_id,
                    "provider": prov,
                    "thread_id": thread_id,
                }
                req_headers = {"X-Request-ID": f"req_{uuid.uuid4().hex[:12]}"}
                if effective_ua:
                    req_headers["User-Agent"] = effective_ua

                try:
                    r = self._http.post(
                        self._url("/api/v1/search/stream"),
                        json=payload,
                        headers=req_headers,
                        stream=True,
                        timeout=self.timeout,
                    )
                except requests.exceptions.Timeout as te:
                    raise APITimeoutError(f"Stream request timed out: {te}") from te
                except requests.exceptions.ConnectionError as ce:
                    raise APIConnectionError(f"Connection failed: {ce}") from ce

                if r.status_code >= 400:
                    self._handle_response_error(r)

                accumulated_answer = ""
                final_sources: list[SourceItem] = []

                with r:
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
                            event_type = chunk_data.get("type") or chunk_data.get("event", "delta")
                            delta = chunk_data.get("delta", "")
                            content = chunk_data.get("content", "")
                            thinking = chunk_data.get("thinking")
                            if delta:
                                accumulated_answer += delta
                            sources_raw = chunk_data.get("sources", [])
                            if sources_raw:
                                final_sources = [SourceItem(**s) for s in sources_raw]

                            chunk = StreamChunk(
                                event=event_type,
                                type=event_type,
                                delta=delta,
                                content=content,
                                thinking=thinking,
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
            except Exception as e:
                last_err = e
                logger.warning("Stream provider '%s' failed: %s", prov, e)
                if prov != providers_to_try[-1]:
                    continue
                raise

        if last_err:
            raise last_err
        raise ProviderError(f"All stream providers failed: {providers_to_try}")

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
        try:
            res = self._http.post(self._url("/api/v1/sessions"), json=payload, timeout=self.timeout)
        except requests.exceptions.Timeout as te:
            raise APITimeoutError(f"Session creation timed out: {te}") from te
        except requests.exceptions.ConnectionError as ce:
            raise APIConnectionError(f"Session creation connection failed: {ce}") from ce

        if res.status_code >= 400:
            self._handle_response_error(res)

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

        try:
            res = self._http.get(self._url(f"/api/v1/sessions/{session_id}"), timeout=self.timeout)
        except requests.exceptions.Timeout as te:
            raise APITimeoutError(f"Session fetch timed out: {te}") from te
        except requests.exceptions.ConnectionError as ce:
            raise APIConnectionError(f"Session fetch connection failed: {ce}") from ce

        if res.status_code == 404:
            return None
        if res.status_code >= 400:
            self._handle_response_error(res)

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

        try:
            res = self._http.get(self._url("/api/v1/sessions"), timeout=self.timeout)
        except requests.exceptions.Timeout as te:
            raise APITimeoutError(f"Session listing timed out: {te}") from te
        except requests.exceptions.ConnectionError as ce:
            raise APIConnectionError(f"Session listing connection failed: {ce}") from ce

        if res.status_code >= 400:
            self._handle_response_error(res)

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

        try:
            res = self._http.delete(self._url(f"/api/v1/sessions/{session_id}"), timeout=self.timeout)
        except requests.exceptions.Timeout as te:
            raise APITimeoutError(f"Session delete timed out: {te}") from te
        except requests.exceptions.ConnectionError as ce:
            raise APIConnectionError(f"Session delete connection failed: {ce}") from ce

        if res.status_code == 404:
            return False
        if res.status_code >= 400:
            self._handle_response_error(res)
        return res.status_code == 200

    def _clear_sessions(self) -> int:
        if self._engine is not None and not self.base_url:
            return self._engine.session_store.clear_all()

        try:
            res = self._http.post(self._url("/api/v1/sessions/clear"), timeout=self.timeout)
        except requests.exceptions.Timeout as te:
            raise APITimeoutError(f"Clear sessions timed out: {te}") from te
        except requests.exceptions.ConnectionError as ce:
            raise APIConnectionError(f"Clear sessions connection failed: {ce}") from ce

        if res.status_code >= 400:
            self._handle_response_error(res)
        return res.json().get("cleared", 0)

    # -------------------------------------------------------------------------
    # Top-level Ergonomic Shortcuts
    # -------------------------------------------------------------------------

    def query(
        self,
        query: str,
        session_id: str | None = None,
        provider: str | None = None,
        timeout: float | tuple[float, float] | None = None,
        fallback: str | list[str] | None = None,
    ) -> SearchResponse:
        """Top-level shorthand for query with optional fallback and timeout."""
        return self.search.query(
            query=query,
            session_id=session_id,
            provider=provider,
            timeout=timeout,
            fallback=fallback,
        )

    def stream(
        self,
        query: str,
        session_id: str | None = None,
        provider: str | None = None,
        fallback: str | list[str] | None = None,
    ) -> Generator[StreamChunk, None, SearchResponse]:
        """Top-level shorthand for streaming with optional fallback."""
        return self.search.stream(
            query=query,
            session_id=session_id,
            provider=provider,
            fallback=fallback,
        )

    def chat(
        self,
        query: str,
        session_id: str | None = None,
        title: str | None = None,
        provider: str | None = None,
        fallback: str | list[str] | None = None,
    ) -> SearchResponse:
        """Convenient multi-turn chat wrapper with optional fallback."""
        if not session_id:
            sess = self.sessions.create(title=title or "Chat Session")
            session_id = sess.session_id
        return self.sessions.query(
            session_id=session_id,
            query=query,
            provider=provider,
            fallback=fallback,
        )

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
        rules: list[Any] | Any | None = None,
        mcp_clients: list[Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Create an autonomous AI Agent with model based on provider, tools, rules, PDF creation, and MCP support."""
        from .agent import Agent
        return Agent(
            name=name,
            provider=provider,
            model=model,
            instructions=instructions,
            client=self,
            tools=tools,
            rules=rules or self.rules,
            mcp_clients=mcp_clients,
            **kwargs,
        )

    def agent(
        self,
        provider: str = "google",
        model: str | None = None,
        instructions: str | None = None,
        tools: list[Any] | None = None,
        rules: list[Any] | Any | None = None,
        **kwargs: Any,
    ) -> Any:
        """Shorthand to create an autonomous AI Agent."""
        return self.create_agent(
            provider=provider,
            model=model,
            instructions=instructions,
            tools=tools,
            rules=rules,
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
