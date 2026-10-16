"""Client configuration for Grip SDK."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Config:
    """Client connection, resilience, and behavior configuration."""

    api_base_url: str = ""
    timeout: float = 45.0
    connect_timeout: float | None = None
    read_timeout: float | None = None
    api_key: str | None = None
    default_provider: str = "google"
    max_retries: int = 3
    retry_backoff: float = 0.5
    pool_connections: int = 25
    pool_maxsize: int = 50
    fallback_providers: list[str] = field(default_factory=list)
    cache_enabled: bool = True
    cache_ttl: int = 3600
    user_agent: str | None = None

    @classmethod
    def from_env(cls) -> Config:
        fallbacks_str = os.getenv("GRIP_FALLBACK_PROVIDERS", "")
        fallbacks = [p.strip() for p in fallbacks_str.split(",") if p.strip()]

        return cls(
            api_base_url=os.getenv("GRIP_API_URL", os.getenv("API_BASE_URL", "")),
            timeout=float(os.getenv("GRIP_TIMEOUT", "45.0")),
            api_key=os.getenv("GRIP_API_KEY"),
            default_provider=os.getenv("GRIP_DEFAULT_PROVIDER", "google"),
            max_retries=int(os.getenv("GRIP_MAX_RETRIES", "3")),
            retry_backoff=float(os.getenv("GRIP_RETRY_BACKOFF", "0.5")),
            pool_connections=int(os.getenv("GRIP_POOL_CONNECTIONS", "25")),
            pool_maxsize=int(os.getenv("GRIP_POOL_MAXSIZE", "50")),
            fallback_providers=fallbacks,
            cache_enabled=os.getenv("GRIP_CACHE_ENABLED", "true").lower() in ("1", "true", "yes"),
            cache_ttl=int(os.getenv("GRIP_CACHE_TTL", "3600")),
            user_agent=os.getenv("GRIP_USER_AGENT", os.getenv("USER_AGENT_OVERRIDE")),
        )


ClientConfig = Config


def get_config() -> Config:
    return Config.from_env()


__all__ = ["Config", "ClientConfig", "get_config"]

