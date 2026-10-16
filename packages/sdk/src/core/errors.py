"""Standard exception hierarchy for Grip Platform."""

from __future__ import annotations


class GripError(Exception):
    """Base exception for all Grip Platform errors."""


class ProviderError(GripError):
    """Raised when an underlying AI search provider (Google, OpenAI, etc.) encounters an error."""


class QuotaExceededError(ProviderError):
    """Raised when rate limits or quotas are exceeded by an upstream provider."""


RateLimitError = QuotaExceededError


class BotBlockedError(GripError):
    """Raised when browser automation encounters CAPTCHA or bot verification challenges."""


class SessionNotFoundError(GripError):
    """Raised when a requested multi-turn conversation session is missing or expired."""


class ConfigError(GripError):
    """Raised when invalid or missing configuration parameters are encountered."""


class ValidationError(GripError):
    """Raised when request payload or query parameters fail validation."""


class APIStatusError(ProviderError):
    """Raised when an API endpoint returns an HTTP error code >= 400."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        body: str | dict | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body
        self.request_id = request_id


class AuthenticationError(GripError):
    """Raised when authentication credentials (API key) are invalid, expired, or missing."""


class APIConnectionError(GripError):
    """Raised when network connectivity or socket connection to Grip services fails."""


class APITimeoutError(GripError):
    """Raised when an API request, generation, or streaming socket times out."""


class NotFoundError(GripError):
    """Raised when a requested endpoint, model, or resource does not exist."""


# Backwards-compatibility alias
GoogleAISearchError = GripError

