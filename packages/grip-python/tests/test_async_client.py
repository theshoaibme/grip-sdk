"""Tests for Grip asynchronous client."""

import asyncio
from unittest.mock import MagicMock

from grip import AsyncGrip, SearchResponse, StreamChunk


def test_async_grip_initialization():
    async def _test():
        client = AsyncGrip()
        assert client.provider == "google"
        assert client.search is not None
        assert client.sessions is not None
        await client.close()

    asyncio.run(_test())


def test_async_grip_query_mock():
    async def _test():
        mock_engine = MagicMock()
        mock_engine.search.return_value = SearchResponse(
            answer="Async answer",
            sources=[],
            query="test",
            status="success",
        )

        client = AsyncGrip(engine=mock_engine)
        res = await client.search.query("test")
        assert res.answer == "Async answer"
        await client.close()

    asyncio.run(_test())


def test_async_grip_stream_mock():
    async def _test():
        mock_engine = MagicMock()
        mock_engine.stream_search.return_value = iter([
            StreamChunk(type="delta", delta="Async "),
            StreamChunk(type="delta", delta="Stream"),
        ])

        client = AsyncGrip(engine=mock_engine)
        chunks = []
        async for c in client.search.stream("test"):
            chunks.append(c.delta)

        assert "".join(chunks) == "Async Stream"
        await client.close()

    asyncio.run(_test())
