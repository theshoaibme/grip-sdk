"""Unified configuration model for Grip Platform."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GripConfig:
    """Configuration settings for Grip Platform and providers."""

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Provider routing (dynamic default)
    default_provider: str = "google"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"

    # Browser & engine settings
    browser_headless: bool = True
    browser_channel: str = "chrome"
    browser_timeout: int = 45
    browser_lang: str = "en"
    browser_gl: str = "us"
    browser_user_data_dir: str = ".chrome-profile"
    user_agent_override: str = ""
    proxy_server: str | None = None
    proxy_username: str | None = None
    proxy_password: str | None = None
    proxy_bypass: str | None = None

    # Fallback and verification
    fallback_on_block: bool = True
    antibot_stealth: bool = True

    # Cache and Rate Limiting
    cache_ttl: int = 300
    cache_max_entries: int = 1000
    session_ttl_sec: int = 3600
    request_timeout: int = 15
    stream_delay_ms: int = 20
    rate_limit_capacity: int = 60
    rate_limit_refill_per_sec: float = 1.0

    @classmethod
    def from_env(cls) -> GripConfig:
        """Load configuration from environment variables."""
        return cls(
            host=os.getenv("HOST", os.getenv("GRIP_HOST", "0.0.0.0")),
            port=int(os.getenv("PORT", os.getenv("GRIP_PORT", "8000"))),
            debug=os.getenv("DEBUG", os.getenv("GRIP_DEBUG", "0")).lower() in ("1", "true", "yes"),
            default_provider=os.getenv("GRIP_DEFAULT_PROVIDER", "google"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            browser_headless=os.getenv("BROWSER_HEADLESS", "1").lower() not in ("0", "false", "no"),
            browser_channel=os.getenv("BROWSER_CHANNEL", "chrome"),
            browser_timeout=int(os.getenv("BROWSER_TIMEOUT", "45")),
            browser_lang=os.getenv("BROWSER_LANG", "en"),
            browser_gl=os.getenv("BROWSER_GL", "us"),
            browser_user_data_dir=os.getenv("BROWSER_USER_DATA_DIR", ".chrome-profile"),
            user_agent_override=os.getenv("USER_AGENT_OVERRIDE", ""),
            proxy_server=os.getenv("PROXY_SERVER"),
            proxy_username=os.getenv("PROXY_USERNAME"),
            proxy_password=os.getenv("PROXY_PASSWORD"),
            proxy_bypass=os.getenv("PROXY_BYPASS"),
            fallback_on_block=os.getenv("FALLBACK_ON_BLOCK", "1").lower() in ("1", "true", "yes"),
            antibot_stealth=os.getenv("ANTIBOT_STEALTH", "1").lower() in ("1", "true", "yes"),
            cache_ttl=int(os.getenv("CACHE_TTL", "300")),
            cache_max_entries=int(os.getenv("CACHE_MAX_ENTRIES", "1000")),
            session_ttl_sec=int(os.getenv("SESSION_TTL_SEC", "3600")),
            request_timeout=int(os.getenv("REQUEST_TIMEOUT", "15")),
            stream_delay_ms=int(os.getenv("STREAM_DELAY_MS", "20")),
            rate_limit_capacity=int(os.getenv("RATE_LIMIT_CAPACITY", "60")),
            rate_limit_refill_per_sec=float(os.getenv("RATE_LIMIT_REFILL_PER_SEC", "1.0")),
        )


def load_config() -> GripConfig:
    """Convenience helper to retrieve active configuration."""
    return GripConfig.from_env()
