"""Client configuration for Grip SDK."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Config:
    """Client connection and behavior configuration."""

    api_base_url: str = "http://localhost:8000"
    timeout: float = 45.0
    api_key: str | None = None
    default_provider: str = "google"

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            api_base_url=os.getenv("GRIP_API_URL", os.getenv("API_BASE_URL", "http://localhost:8000")),
            timeout=float(os.getenv("GRIP_TIMEOUT", "45.0")),
            api_key=os.getenv("GRIP_API_KEY"),
            default_provider=os.getenv("GRIP_DEFAULT_PROVIDER", "google"),
        )


ClientConfig = Config


def get_config() -> Config:
    return Config.from_env()


__all__ = ["Config", "ClientConfig", "get_config"]
