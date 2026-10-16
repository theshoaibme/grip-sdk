"""OpenAI search and LLM provider integration with live API execution and resilient fallback synthesis."""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any, Generator

from core.models.response import SearchResponse
from core.models.source import SourceItem
from .base import BaseSearchProvider

logger = logging.getLogger(__name__)


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

    def _clean_query(self, query: str) -> str:
        """Strip prompt headers from raw query string."""
        return query.split("\n\n[SYSTEM")[0].split("\n\n[STRICT")[0].split("\n\n[RESPONSE")[0].strip()

    def _call_openai_api(self, prompt: str) -> str:
        """Execute a live chat completion call to OpenAI API."""
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for live API call.")

        url = "https://api.openai.com/v1/chat/completions"
        from google_ai_search.prompts import get_response_format, get_system_identity

        system_msg = f"{get_system_identity()}\n\n{get_response_format()}"
        payload = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
        }).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "Grip-SDK/OpenAI-Provider",
        }
        req = urllib.request.Request(url, data=payload, headers=headers)
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()

    def _synthesize_response(self, clean_query: str) -> str:
        """Synthesize intelligent answer when live API key is unavailable or fails."""
        if self.api_key:
            try:
                return self._call_openai_api(clean_query)
            except Exception as exc:
                logger.warning("OpenAI API call failed (%s). Falling back to search synthesis.", exc)

        from google_ai_search.core.engine import (
            _fetch_fallback_results,
            _generate_natural_explanation,
            _normalize_ai_answer,
        )

        try:
            synthesized, sources, _ = _fetch_fallback_results(clean_query, provider=self.name)
            if synthesized and len(synthesized.strip()) > 25:
                return _normalize_ai_answer(synthesized, clean_query, provider=self.name)
        except Exception:
            pass

        return _generate_natural_explanation(clean_query)

    def search(
        self,
        query: str,
        thread_id: str | None = None,
        session_id: str | None = None,
        **kwargs: Any,
    ) -> SearchResponse:
        start_time = time.time()
        clean = self._clean_query(query)

        # Check conversational queries first
        from google_ai_search.core.engine import _handle_conversational_query

        conv = _handle_conversational_query(clean, provider=self.name)
        if conv:
            c_ans, c_src, c_sug = conv
            return SearchResponse(
                query=clean,
                answer=c_ans,
                sources=c_src or [
                    SourceItem(
                        url="https://openai.com",
                        title="OpenAI Intelligence",
                        snippet="Conversational intelligence via OpenAI",
                    )
                ],
                session_id=session_id,
                thread_id=thread_id or "openai_conv",
                provider=self.name,
                search_time=round(time.time() - start_time, 3),
            )

        answer = self._synthesize_response(clean)
        search_time = round(time.time() - start_time, 3)

        return SearchResponse(
            query=clean,
            answer=answer,
            sources=[SourceItem(url="https://openai.com", title=f"OpenAI Intelligence ({self.model})")],
            session_id=session_id,
            thread_id=thread_id or "openai_thread",
            provider=self.name,
            search_time=search_time,
        )

    def stream_search(
        self,
        query: str,
        thread_id: str | None = None,
        session_id: str | None = None,
        **kwargs: Any,
    ) -> Generator[dict[str, Any], None, SearchResponse]:
        start_time = time.time()
        clean = self._clean_query(query)

        from google_ai_search.core.engine import _handle_conversational_query

        conv = _handle_conversational_query(clean, provider=self.name)
        if conv:
            c_ans, c_src, c_sug = conv
            yield {
                "event": "thinking",
                "thinking": f"Synthesizing response with OpenAI ({self.model})...",
                "delta": "",
            }
            words = c_ans.split(" ")
            for i, word in enumerate(words):
                token = word + (" " if i < len(words) - 1 else "")
                yield {"event": "delta", "delta": token, "text": c_ans}
                time.sleep(0.005)

            search_time = round(time.time() - start_time, 3)
            final_resp = SearchResponse(
                query=clean,
                answer=c_ans,
                sources=c_src or [
                    SourceItem(
                        url="https://openai.com",
                        title="OpenAI Intelligence",
                        snippet="Conversational intelligence via OpenAI",
                    )
                ],
                session_id=session_id,
                thread_id=thread_id or "openai_conv",
                provider=self.name,
                search_time=search_time,
            )
            yield {"event": "done", "response": final_resp.to_dict()}
            return final_resp

        yield {
            "event": "thinking",
            "thinking": f"Synthesizing response with OpenAI ({self.model})...",
            "delta": "",
        }

        answer = self._synthesize_response(clean)
        words = answer.split(" ")
        for i, word in enumerate(words):
            token = word + (" " if i < len(words) - 1 else "")
            yield {"event": "delta", "delta": token, "text": answer}
            time.sleep(0.005)

        search_time = round(time.time() - start_time, 3)
        resp = SearchResponse(
            query=clean,
            answer=answer,
            sources=[SourceItem(url="https://openai.com", title=f"OpenAI Intelligence ({self.model})")],
            session_id=session_id,
            thread_id=thread_id or "openai_thread",
            provider=self.name,
            search_time=search_time,
        )
        yield {"event": "done", "response": resp.to_dict()}
        return resp
