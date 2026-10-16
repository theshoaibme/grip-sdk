"""Google AI Mode search provider with Playwright browser automation and stealth."""

from __future__ import annotations

from typing import Any, Generator
from google_ai_search.core.engine import GoogleAIModeEngine
from google_ai_search.config import Config, get_config
from core.models.response import SearchResponse
from .base import BaseSearchProvider


class GoogleSearchProvider(BaseSearchProvider):
    """Search provider backed by Google AI Mode."""

    def __init__(self, cfg: Config | Any | None = None, name: str = "google") -> None:
        super().__init__(name=name)
        if isinstance(cfg, Config):
            self.config = cfg
        elif cfg is not None:
            c = get_config()
            for key in [
                "browser_headless",
                "browser_user_data_dir",
                "browser_channel",
                "browser_timeout",
                "browser_lang",
                "browser_gl",
                "user_agent_override",
                "proxy_server",
                "proxy_username",
                "proxy_password",
                "fallback_on_block",
                "session_ttl_sec",
                "rate_limit_capacity",
                "rate_limit_refill_per_sec",
                "cache_ttl",
                "cache_max_entries",
                "stream_delay_ms",
            ]:
                if hasattr(cfg, key):
                    val = getattr(cfg, key)
                    if val is not None:
                        setattr(c, key, val)
            self.config = c
        else:
            self.config = get_config()
        self._engine = GoogleAIModeEngine(cfg=self.config)

    def ready(self) -> tuple[bool, str]:
        return self._engine.ready()

    def search(
        self,
        query: str,
        thread_id: str | None = None,
        session_id: str | None = None,
        user_agent: str | None = None,
        **kwargs: Any,
    ) -> SearchResponse:
        return self._engine.search(
            query=query,
            thread_id=thread_id,
            session_id=session_id,
            user_agent=user_agent,
        )

    def stream_search(
        self,
        query: str,
        thread_id: str | None = None,
        session_id: str | None = None,
        user_agent: str | None = None,
        **kwargs: Any,
    ) -> Generator[dict[str, Any], None, SearchResponse]:
        return self._engine.stream_search(
            query=query,
            thread_id=thread_id,
            session_id=session_id,
            user_agent=user_agent,
        )
