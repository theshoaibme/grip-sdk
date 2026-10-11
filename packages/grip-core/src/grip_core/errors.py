"""Standard exception hierarchy for Grip Platform."""

from __future__ import annotations


class GripError(Exception):
    """Base exception for all Grip Platform errors."""


class ProviderError(GripError):
    """Raised when an underlying AI search provider (Google, OpenAI, etc.) encounters an error."""


class QuotaExceededError(ProviderError):
    """Raised when rate limits or quotas are exceeded by an upstream provider."""


class BotBlockedError(GripError):
    """Raised when browser automation encounters CAPTCHA or bot verification challenges."""


class SessionNotFoundError(GripError):
    """Raised when a requested multi-turn conversation session is missing or expired."""


class ConfigError(GripError):
    """Raised when invalid or missing configuration parameters are encountered."""


class ValidationError(GripError):
    """Raised when request payload or query parameters fail validation."""


# Backwards-compatibility alias
GoogleAISearchError = GripError
