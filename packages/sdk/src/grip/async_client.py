"""Grip Python SDK Asynchronous Client.

Enterprise asynchronous AI Search, Provider Agnostic Orchestration,
and Multi-turn Conversational Sessions.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

from grip_core.config import GripConfig, load_config
from grip_core.models.response import Metadata, SearchResponse, StreamChunk
from grip_core.models.session import SessionDetail, SessionSummary
from grip_core.models.source import SourceItem

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
        timeout: float = 60.0,
    ) -> None:
        self._sync_client = Grip(
            base_url=base_url,
            api_key=api_key,
            config=config,
            engine=engine,
            provider=provider,
            timeout=timeout,
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
        timeout: float | None = None,
        user_agent: str | None = None,
    ) -> SearchResponse:
        return await asyncio.to_thread(
            self._sync_client._execute_query,
            query=query,
            session_id=session_id,
            provider=provider or self.provider,
            thread_id=thread_id,
            timeout=timeout,
            user_agent=user_agent,
        )

    async def _execute_stream(
        self,
        query: str,
        session_id: str | None = None,
        provider: str | None = None,
        thread_id: str | None = None,
        user_agent: str | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        def _get_chunks() -> list[StreamChunk]:
            return list(
                self._sync_client._execute_stream(
                    query=query,
                    session_id=session_id,
                    provider=provider or self.provider,
                    thread_id=thread_id,
                    user_agent=user_agent,
                )
            )

        chunks = await asyncio.to_thread(_get_chunks)
        for chunk in chunks:
            yield chunk

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
        timeout: float | None = None,
    ) -> SearchResponse:
        return await self.search.query(
            query=query,
            session_id=session_id,
            provider=provider,
            timeout=timeout,
        )

    async def stream(
        self,
        query: str,
        session_id: str | None = None,
        provider: str | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        async for chunk in self.search.stream(
            query=query,
            session_id=session_id,
            provider=provider,
        ):
            yield chunk

    async def close(self) -> None:
        await asyncio.to_thread(self._sync_client.close)

    async def __aenter__(self) -> AsyncGrip:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()


AsyncClient = AsyncGrip
AsyncGripClient = AsyncGrip
