"""Built-in safe tools for Grip Engine."""

from __future__ import annotations

from google_ai_search.tools.base import ToolRegistry
from google_ai_search.tools.builtin import (
    calculator,
    citation_verifier,
    json_extractor,
    page_fetcher,
    summarizer,
    unit_converter,
)


def register_builtin_tools(registry: ToolRegistry) -> None:
    registry.load_builtins()


__all__ = [
    "calculator",
    "citation_verifier",
    "page_fetcher",
    "summarizer",
    "json_extractor",
    "unit_converter",
    "register_builtin_tools",
]
