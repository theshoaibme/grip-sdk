"""Response formatting registry and utility functions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .base import BaseFormatter
from .citations import CitationFormatter
from .html import HTMLFormatter
from .json import JSONFormatter
from .markdown import MarkdownFormatter
from .text import TextFormatter

if TYPE_CHECKING:
    from ..types.response import SearchResponse


class FormatterRegistry:
    """Registry managing response formatters."""

    def __init__(self) -> None:
        self._formatters: dict[str, Any] = {
            "markdown": MarkdownFormatter(),
            "md": MarkdownFormatter(),
            "json": JSONFormatter(),
            "citation": CitationFormatter(),
            "citations": CitationFormatter(),
            "apa": CitationFormatter(),
            "bibtex": CitationFormatter(),
            "footnotes": CitationFormatter(),
            "html": HTMLFormatter(),
            "text": TextFormatter(),
            "plain": TextFormatter(),
        }

    def register(self, name: str, formatter: Any) -> None:
        self._formatters[name.lower().strip()] = formatter

    def get(self, name: str) -> Any:
        return self._formatters.get(name.lower().strip())

    def format(self, response: SearchResponse, format_name: str = "markdown", **kwargs: Any) -> Any:
        citation_style = kwargs.pop("citation_style", None) or (kwargs.pop("style", None) if format_name in ("citation", "citations") else None)
        formatter = self.get(format_name)
        if not formatter:
            raise ValueError(f"Unknown formatter style: '{format_name}'. Available: {list(self._formatters.keys())}")
        if isinstance(formatter, CitationFormatter):
            if citation_style:
                kwargs["style"] = citation_style
            elif format_name in ("apa", "bibtex", "footnotes", "chicago"):
                kwargs["style"] = format_name
        return formatter.format(response, **kwargs)


_DEFAULT_REGISTRY = FormatterRegistry()


def format_response(response: SearchResponse, format_name: str = "markdown", **kwargs: Any) -> Any:
    """Convenience helper to format a SearchResponse."""
    return _DEFAULT_REGISTRY.format(response, format_name=format_name, **kwargs)


__all__ = [
    "BaseFormatter",
    "MarkdownFormatter",
    "CitationFormatter",
    "JSONFormatter",
    "HTMLFormatter",
    "TextFormatter",
    "FormatterRegistry",
    "format_response",
]
