"""Grip: Enterprise AI Search, Dynamic Provider Orchestration, and Multi-Agent SDK.

https://grip.theshoaib.me/
"""

from __future__ import annotations

from ._version import __version__
from .async_client import AsyncClient, AsyncGrip, AsyncGripClient
from .client import Client, Grip, GripClient
from .config import ClientConfig, Config, get_config
from .exceptions import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BotBlockedError,
    ConfigurationError,
    GripError,
    NotFoundError,
    ProviderError,
    QuotaExceededError,
    RateLimitError,
    SessionNotFoundError,
    ValidationError,
)
from .agent import Agent, AgentResult, AgentStep, MCPClient
from .types import (
    Metadata,
    SearchResponse,
    SessionDetail,
    SessionMessage,
    SessionSummary,
    SourceItem,
    StreamChunk,
)
try:
    from grip_engine.infrastructure.cache import TTLCache
    from grip_engine.infrastructure.rate_limit import RateLimiter
except ImportError:
    TTLCache = None  # type: ignore[assignment, misc]
    RateLimiter = None  # type: ignore[assignment, misc]


__all__ = [
    "__version__",
    "Grip",
    "Client",
    "GripClient",
    "AsyncGrip",
    "AsyncClient",
    "AsyncGripClient",
    "Agent",
    "AgentResult",
    "AgentStep",
    "MCPClient",
    "Config",
    "ClientConfig",
    "get_config",
    "RateLimiter",
    "TTLCache",
    "SearchResponse",
    "StreamChunk",
    "Metadata",
    "SourceItem",
    "SessionDetail",
    "SessionSummary",
    "SessionMessage",
    "GripError",
    "ProviderError",
    "QuotaExceededError",
    "RateLimitError",
    "BotBlockedError",
    "SessionNotFoundError",
    "ConfigError",
    "ConfigurationError",
    "ValidationError",
    "APIStatusError",
    "AuthenticationError",
    "APIConnectionError",
    "APITimeoutError",
    "NotFoundError",
]

