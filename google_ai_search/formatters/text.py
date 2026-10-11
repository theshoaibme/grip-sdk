"""Clean plain text response formatter for CLI and terminal output."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..types.response import SearchResponse


class TextFormatter:
    """Format SearchResponse into clean plain text for CLI usage."""

    def format(
        self,
        response: SearchResponse,
        include_thinking: bool = False,
        include_sources: bool = True,
        **kwargs: Any,
    ) -> str:
        parts: list[str] = []

        if include_thinking and response.thinking:
            parts.append(f"[thinking]\n{response.thinking}\n")

        parts.append(response.answer.strip())

        if include_sources and response.sources:
            parts.append("\nsources:")
            for idx, s in enumerate(response.sources, start=1):
                parts.append(f"  [{idx}] {s.title} ({s.link})")

        return "\n".join(parts)
