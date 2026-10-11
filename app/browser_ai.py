"""Re-export Google AI Mode provider from google_ai_search."""

from google_ai_search.engine import (
    ANSWER_SELECTOR,
    COMPLETE_SELECTOR,
    SEARCH_URL,
    THREAD_SELECTOR,
    GoogleAIModeEngine,
)

GoogleAIModeProvider = GoogleAIModeEngine

__all__ = [
    "GoogleAIModeProvider",
    "GoogleAIModeEngine",
    "SEARCH_URL",
    "ANSWER_SELECTOR",
    "THREAD_SELECTOR",
    "COMPLETE_SELECTOR",
]
