"""Client exception definitions."""

from grip_core.errors import (
    BotBlockedError,
    ConfigError,
    GripError,
    ProviderError,
    QuotaExceededError,
    SessionNotFoundError,
    ValidationError,
)

__all__ = [
    "GripError",
    "ProviderError",
    "QuotaExceededError",
    "BotBlockedError",
    "SessionNotFoundError",
    "ConfigError",
    "ConfigurationError",
    "ValidationError",
]

ConfigurationError = ConfigError
