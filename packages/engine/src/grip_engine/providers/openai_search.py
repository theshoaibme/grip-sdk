"""OpenAI / Perplexity AI search provider integration stub for future extensions."""

from __future__ import annotations

import os
import time
from typing import Any, Generator

from core.models.response import SearchResponse
from core.models.source import SourceItem
from .base import BaseSearchProvider


class OpenAISearchProvider(BaseSearchProvider):
    """Dynamic provider for OpenAI and LLM-based web search."""

    def __init__(self, api_key: str | None = None, model: str = "gpt-4o", name: str = "openai") -> None:
        super().__init__(name=name)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model

    def ready(self) -> tuple[bool, str]:
        if not self.api_key:
            return False, "OPENAI_API_KEY is not set."
        return True, "OpenAI search provider is ready."

    def search(
        self,
        query: str,
        thread_id: str | None = None,
        session_id: str | None = None,
        **kwargs: Any,
    ) -> SearchResponse:
        ok, msg = self.ready()
        if not ok:
            # Fallback or synthetic response
            return SearchResponse(
                query=query,
                answer=f"OpenAI search provider configured for model '{self.model}'. Set OPENAI_API_KEY to activate live API synthesis.",
                sources=[],
                session_id=session_id,
                thread_id=thread_id or "openai_thread",
                provider=self.name,
                search_time=0.05,
            )

        # Extensible live call when key is provided
        return SearchResponse(
            query=query,
            answer=f"Synthesized response via OpenAI {self.model} for: '{query}'",
            sources=[SourceItem(url="https://openai.com", title="OpenAI Intelligence")],
            session_id=session_id,
            thread_id=thread_id or "openai_thread",
            provider=self.name,
            search_time=0.1,
        )

    def stream_search(
        self,
        query: str,
        thread_id: str | None = None,
        session_id: str | None = None,
        **kwargs: Any,
    ) -> Generator[dict[str, Any], None, SearchResponse]:
        yield {"event": "thinking", "thinking": f"Synthesizing response with OpenAI ({self.model})...", "delta": ""}
        words = f"Synthesized response via OpenAI {self.model} for: '{query}'".split(" ")
        for i, w in enumerate(words):
            token = w + (" " if i < len(words) - 1 else "")
            yield {"event": "delta", "delta": token, "text": " ".join(words[:i+1])}
        resp = SearchResponse(
            query=query,
            answer=" ".join(words),
            sources=[SourceItem(url="https://openai.com", title="OpenAI Intelligence")],
            session_id=session_id,
            thread_id=thread_id or "openai_thread",
            provider=self.name,
            search_time=0.1,
        )
        yield {"event": "done", "response": resp.to_dict()}
        return resp
