"""Client exception definitions."""

from core.errors import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BotBlockedError,
    ConfigError,
    GripError,
    NotFoundError,
    ProviderError,
    QuotaExceededError,
    RateLimitError,
    SessionNotFoundError,
    ValidationError,
)

__all__ = [
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

ConfigurationError = ConfigError

