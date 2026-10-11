"""Exception hierarchy for Google AI Search library."""


class GoogleAISearchError(Exception):
    """Base exception for all Google AI Search errors."""


GripError = GoogleAISearchError


class ProviderError(GoogleAISearchError):
    """Raised when the underlying AI search provider encounters an error."""


class QuotaExceededError(ProviderError):
    """Raised when rate limits or quotas are exceeded by upstream provider."""


class BotBlockedError(GoogleAISearchError):
    """Raised when Google blocks automated browser traffic (CAPTCHA or bot check)."""


class SessionNotFoundError(GoogleAISearchError):
    """Raised when a requested session is not found or has expired."""


class ConfigError(GoogleAISearchError):
    """Raised when invalid or missing configuration is encountered."""
