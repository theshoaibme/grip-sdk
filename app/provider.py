"""Google AI Browser Mode provider adapter module.

Exclusively uses Google AI Search (udm=50 AI Mode rendered via Chromium).
No API keys required.
"""

from google_ai_search.engine import GoogleAIModeEngine
from google_ai_search.exceptions import (
    ConfigError,
    GoogleAISearchError,
    ProviderError,
    QuotaExceededError,
)
from google_ai_search.models import SearchResponse, SourceItem

QuotaExceeded = QuotaExceededError
GoogleAIModeProvider = GoogleAIModeEngine


def build_answer_provider(cfg=None):
    """Instantiate the Google AI Browser Mode engine."""
    from google_ai_search.config import get_config
    c = cfg or get_config()
    return GoogleAIModeEngine(c)


def build_provider(cfg=None):
    """Backwards compatibility: only Google AI Browser Mode is supported."""
    return build_answer_provider(cfg)
