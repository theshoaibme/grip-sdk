"""Grip Python SDK Asynchronous Client.

Enterprise asynchronous AI Search, Provider Agnostic Orchestration,
and Multi-turn Conversational Sessions.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

from core.config import GripConfig, load_config
from core.models.response import Metadata, SearchResponse, StreamChunk
from core.models.session import SessionDetail, SessionSummary
from core.models.source import SourceItem

from .client import Grip
from .config import ClientConfig
from .resources.search import AsyncSearchResource
from .resources.sessions import AsyncSessionsResource


class AsyncGrip:
    """Primary asynchronous client for Grip Platform.

    Usage:
        >>> import asyncio
        >>> from grip import AsyncGrip
        >>>
        >>> async def main():
        ...     client = AsyncGrip()
        ...     response = await client.search.query("Quantum computing breakthroughs")
        ...     print(response.answer)
        ...     await client.close()
        >>> asyncio.run(main())
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
        self._sync_client = Grip(
            base_url=base_url,
            api_key=api_key,
            config=config,
            engine=engine,
            provider=provider,
            timeout=timeout,
            user_agent=user_agent,
            use_system_profile=use_system_profile,
            chrome_profile_dir=chrome_profile_dir,
            cache=cache,
            cache_ttl=cache_ttl,
            low_latency=low_latency,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize,
            fallback_providers=fallback_providers,
        )
        self.provider = provider
        self.search = AsyncSearchResource(client=self)
        self.sessions = AsyncSessionsResource(client=self)

    async def _execute_query(
        self,
        query: str,
        session_id: str | None = None,
        provider: str | None = None,
        thread_id: str | None = None,
        timeout: float | tuple[float, float] | None = None,
        user_agent: str | None = None,
        fallback: str | list[str] | None = None,
    ) -> SearchResponse:
        return await asyncio.to_thread(
            self._sync_client._execute_query,
            query=query,
            session_id=session_id,
            provider=provider or self.provider,
            thread_id=thread_id,
            timeout=timeout,
            user_agent=user_agent,
            fallback=fallback,
        )

    async def _execute_stream(
        self,
        query: str,
        session_id: str | None = None,
        provider: str | None = None,
        thread_id: str | None = None,
        user_agent: str | None = None,
        fallback: str | list[str] | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue(maxsize=100)
        sentinel = object()

        def _producer() -> None:
            try:
                for chunk in self._sync_client._execute_stream(
                    query=query,
                    session_id=session_id,
                    provider=provider or self.provider,
                    thread_id=thread_id,
                    user_agent=user_agent,
                    fallback=fallback,
                ):
                    fut = asyncio.run_coroutine_threadsafe(queue.put(("chunk", chunk)), loop)
                    fut.result()
            except Exception as exc:
                fut = asyncio.run_coroutine_threadsafe(queue.put(("error", exc)), loop)
                try:
                    fut.result()
                except Exception:
                    pass
            finally:
                fut = asyncio.run_coroutine_threadsafe(queue.put(("done", sentinel)), loop)
                try:
                    fut.result()
                except Exception:
                    pass

        task = loop.run_in_executor(None, _producer)
        try:
            while True:
                msg_type, val = await queue.get()
                queue.task_done()
                if msg_type == "chunk":
                    yield val
                elif msg_type == "error":
                    raise val
                elif msg_type == "done":
                    break
        finally:
            pass

    async def _create_session(
        self,
        title: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionDetail:
        return await asyncio.to_thread(
            self._sync_client._create_session,
            title=title,
            session_id=session_id,
            metadata=metadata,
        )

    async def _get_session(self, session_id: str) -> SessionDetail | None:
        return await asyncio.to_thread(self._sync_client._get_session, session_id)

    async def _list_sessions(self) -> list[SessionSummary]:
        return await asyncio.to_thread(self._sync_client._list_sessions)

    async def _delete_session(self, session_id: str) -> bool:
        return await asyncio.to_thread(self._sync_client._delete_session, session_id)

    async def _clear_sessions(self) -> int:
        return await asyncio.to_thread(self._sync_client._clear_sessions)

    async def query(
        self,
        query: str,
        session_id: str | None = None,
        provider: str | None = None,
        timeout: float | tuple[float, float] | None = None,
        fallback: str | list[str] | None = None,
    ) -> SearchResponse:
        return await self.search.query(
            query=query,
            session_id=session_id,
            provider=provider,
            timeout=timeout,
            fallback=fallback,
        )

    async def stream(
        self,
        query: str,
        session_id: str | None = None,
        provider: str | None = None,
        fallback: str | list[str] | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        async for chunk in self.search.stream(
            query=query,
            session_id=session_id,
            provider=provider,
            fallback=fallback,
        ):
            yield chunk

    async def chat(
        self,
        query: str,
        session_id: str | None = None,
        title: str | None = None,
        provider: str | None = None,
        fallback: str | list[str] | None = None,
    ) -> SearchResponse:
        """Convenient asynchronous multi-turn chat wrapper."""
        if not session_id:
            sess = await self.sessions.create(title=title or "Chat Session")
            session_id = sess.session_id
        return await self.sessions.query(
            session_id=session_id,
            query=query,
            provider=provider,
            fallback=fallback,
        )

    async def close(self) -> None:
        await asyncio.to_thread(self._sync_client.close)

    async def __aenter__(self) -> AsyncGrip:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()


AsyncClient = AsyncGrip
AsyncGripClient = AsyncGrip

