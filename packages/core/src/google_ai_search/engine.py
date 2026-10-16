"""Backward-compatibility re-export for GoogleAIModeEngine from core."""

from .core.engine import (
    ANSWER_SELECTOR,
    COMPLETE_SELECTOR,
    SEARCH_URL,
    THREAD_SELECTOR,
    GoogleAIModeEngine,
)

__all__ = [
    "GoogleAIModeEngine",
    "SEARCH_URL",
    "ANSWER_SELECTOR",
    "THREAD_SELECTOR",
    "COMPLETE_SELECTOR",
]
