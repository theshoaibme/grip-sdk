"""core: Shared domain models, protocols, and security validations for Grip Platform."""

from .config import GripConfig, load_config
from .errors import (
    BotBlockedError,
    ConfigError,
    GripError,
    ProviderError,
    QuotaExceededError,
    SessionNotFoundError,
    ValidationError,
)
from .models import (
    SearchRequest,
    SearchResponse,
    SessionCreateRequest,
    SessionDetail,
    SessionMessage,
    SessionSummary,
    SourceItem,
    StreamChunk,
)
from .protocols import FormatterProtocol, SearchProviderProtocol, SessionStoreProtocol
from .security import sanitize_session_id, validate_query

__version__ = "0.3.4"

__all__ = [
    "GripConfig",
    "load_config",
    "GripError",
    "ProviderError",
    "QuotaExceededError",
    "BotBlockedError",
    "SessionNotFoundError",
    "ConfigError",
    "ValidationError",
    "SearchRequest",
    "SessionCreateRequest",
    "SearchResponse",
    "StreamChunk",
    "SourceItem",
    "SessionMessage",
    "SessionSummary",
    "SessionDetail",
    "SearchProviderProtocol",
    "FormatterProtocol",
    "SessionStoreProtocol",
    "validate_query",
    "sanitize_session_id",
    "__version__",
]
