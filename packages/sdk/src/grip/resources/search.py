"""Search resource for executing Grip AI queries and streams."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from typing import TYPE_CHECKING, Any

from grip_core.models.response import SearchResponse, StreamChunk

if TYPE_CHECKING:
    from ..client import Grip
    from ..async_client import AsyncGrip


class SearchResource:
    """Synchronous resource for search operations."""

    def __init__(self, client: Grip) -> None:
        self._client = client

    def __call__(
        self,
        query: str,
        *,
        session_id: str | None = None,
        provider: str | None = None,
        thread_id: str | None = None,
        timeout: float | None = None,
        user_agent: str | None = None,
    ) -> SearchResponse:
        return self.query(
            query=query,
            session_id=session_id,
            provider=provider,
            thread_id=thread_id,
            timeout=timeout,
            user_agent=user_agent,
        )

    def query(
        self,
        query: str,
        *,
        session_id: str | None = None,
        provider: str | None = None,
        thread_id: str | None = None,
        timeout: float | None = None,
        user_agent: str | None = None,
    ) -> SearchResponse:
        """Execute an AI search query with optional session, provider, and authentic client user_agent."""
        kwargs: dict[str, Any] = {}
        if user_agent is not None:
            kwargs["user_agent"] = user_agent
        return self._client._execute_query(
            query=query,
            session_id=session_id,
            provider=provider,
            thread_id=thread_id,
            timeout=timeout,
            **kwargs,
        )

    def stream(
        self,
        query: str,
        *,
        session_id: str | None = None,
        provider: str | None = None,
        thread_id: str | None = None,
        user_agent: str | None = None,
    ) -> Generator[StreamChunk, None, SearchResponse]:
        """Stream an AI search response token by token with authentic client user_agent."""
        kwargs: dict[str, Any] = {}
        if user_agent is not None:
            kwargs["user_agent"] = user_agent
        return self._client._execute_stream(
            query=query,
            session_id=session_id,
            provider=provider,
            thread_id=thread_id,
            **kwargs,
        )


class AsyncSearchResource:
    """Asynchronous resource for search operations."""

    def __init__(self, client: AsyncGrip) -> None:
        self._client = client

    async def __call__(
        self,
        query: str,
        *,
        session_id: str | None = None,
        provider: str | None = None,
        thread_id: str | None = None,
        timeout: float | None = None,
        user_agent: str | None = None,
    ) -> SearchResponse:
        return await self.query(
            query=query,
            session_id=session_id,
            provider=provider,
            thread_id=thread_id,
            timeout=timeout,
            user_agent=user_agent,
        )

    async def query(
        self,
        query: str,
        *,
        session_id: str | None = None,
        provider: str | None = None,
        thread_id: str | None = None,
        timeout: float | None = None,
        user_agent: str | None = None,
    ) -> SearchResponse:
        """Asynchronously execute an AI search query."""
        kwargs: dict[str, Any] = {}
        if user_agent is not None:
            kwargs["user_agent"] = user_agent
        return await self._client._execute_query(
            query=query,
            session_id=session_id,
            provider=provider,
            thread_id=thread_id,
            timeout=timeout,
            **kwargs,
        )

    async def stream(
        self,
        query: str,
        *,
        session_id: str | None = None,
        provider: str | None = None,
        thread_id: str | None = None,
        user_agent: str | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Asynchronously stream an AI search response."""
        kwargs: dict[str, Any] = {}
        if user_agent is not None:
            kwargs["user_agent"] = user_agent
        async for chunk in self._client._execute_stream(
            query=query,
            session_id=session_id,
            provider=provider,
            thread_id=thread_id,
            **kwargs,
        ):
            yield chunk
