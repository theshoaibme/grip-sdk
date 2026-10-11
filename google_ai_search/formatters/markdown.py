"""Markdown response formatter with thinking accordions and citations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..types.response import SearchResponse


class MarkdownFormatter:
    """Format SearchResponse into rich GitHub-flavored markdown."""

    def format(
        self,
        response: SearchResponse,
        include_thinking: bool = True,
        include_sources: bool = True,
        include_suggestions: bool = True,
        **kwargs: Any,
    ) -> str:
        parts: list[str] = []

        # 1. Thinking / Reasoning trace
        if include_thinking and response.thinking:
            time_str = f" ({response.thinking_time:.2f}s)" if response.thinking_time else ""
            parts.append(
                f"> <details>\n> <summary>💭 <i>thinking trace{time_str}</i></summary>\n>\n"
                + "\n".join(f"> {line}" for line in response.thinking.splitlines())
                + "\n> </details>\n"
            )

        # 2. Main Answer
        parts.append(response.answer.strip())

        # 3. Grounded Sources
        if include_sources and response.sources:
            parts.append("\n### sources")
            for idx, s in enumerate(response.sources, start=1):
                title = s.title.strip() if s.title else s.link
                snippet = f" — *{s.snippet.strip()}*" if s.snippet else ""
                parts.append(f"{idx}. [{title}]({s.link}){snippet}")

        # 4. Suggestions
        if include_suggestions and response.suggestions:
            parts.append("\n### related")
            for sug in response.suggestions:
                parts.append(f"- {sug}")

        return "\n\n".join(parts)
