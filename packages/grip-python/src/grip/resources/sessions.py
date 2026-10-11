"""Sessions resource for conversational session management in Grip SDK."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from typing import TYPE_CHECKING, Any

from grip_core.models.response import SearchResponse, StreamChunk
from grip_core.models.session import SessionDetail, SessionSummary

if TYPE_CHECKING:
    from ..client import Grip
    from ..async_client import AsyncGrip


class SessionsResource:
    """Synchronous resource for multi-turn sessions."""

    def __init__(self, client: Grip) -> None:
        self._client = client

    def create(
        self,
        title: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionDetail:
        return self._client._create_session(title=title, session_id=session_id, metadata=metadata)

    def get(self, session_id: str) -> SessionDetail | None:
        return self._client._get_session(session_id=session_id)

    def list(self) -> list[SessionSummary]:
        return self._client._list_sessions()

    def count(self) -> int:
        return len(self.list())

    def delete(self, session_id: str) -> bool:
        return self._client._delete_session(session_id=session_id)

    def clear(self) -> int:
        return self._client._clear_sessions()

    def query(
        self,
        session_id: str,
        query: str,
        *,
        provider: str | None = None,
        timeout: float | None = None,
    ) -> SearchResponse:
        return self._client._execute_query(
            query=query,
            session_id=session_id,
            provider=provider,
            timeout=timeout,
        )

    def stream(
        self,
        session_id: str,
        query: str,
        *,
        provider: str | None = None,
    ) -> Generator[StreamChunk, None, SearchResponse]:
        return self._client._execute_stream(
            query=query,
            session_id=session_id,
            provider=provider,
        )


class AsyncSessionsResource:
    """Asynchronous resource for multi-turn sessions."""

    def __init__(self, client: AsyncGrip) -> None:
        self._client = client

    async def create(
        self,
        title: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionDetail:
        return await self._client._create_session(title=title, session_id=session_id, metadata=metadata)

    async def get(self, session_id: str) -> SessionDetail | None:
        return await self._client._get_session(session_id=session_id)

    async def list(self) -> list[SessionSummary]:
        return await self._client._list_sessions()

    async def count(self) -> int:
        return len(await self.list())

    async def delete(self, session_id: str) -> bool:
        return await self._client._delete_session(session_id=session_id)

    async def clear(self) -> int:
        return await self._client._clear_sessions()

    async def query(
        self,
        session_id: str,
        query: str,
        *,
        provider: str | None = None,
        timeout: float | None = None,
    ) -> SearchResponse:
        return await self._client._execute_query(
            query=query,
            session_id=session_id,
            provider=provider,
            timeout=timeout,
        )

    async def stream(
        self,
        session_id: str,
        query: str,
        *,
        provider: str | None = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        async for chunk in self._client._execute_stream(
            query=query,
            session_id=session_id,
            provider=provider,
        ):
            yield chunk
