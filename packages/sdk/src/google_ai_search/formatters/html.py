"""Semantic HTML response formatter."""

from __future__ import annotations

import html
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..types.response import SearchResponse


class HTMLFormatter:
    """Format SearchResponse into semantic HTML snippet."""

    def format(
        self,
        response: SearchResponse,
        include_thinking: bool = True,
        include_sources: bool = True,
        **kwargs: Any,
    ) -> str:
        parts: list[str] = ['<article class="google-ai-response">']

        if include_thinking and response.thinking:
            parts.append(
                f'<details class="thinking-block"><summary>thinking trace</summary>'
                f'<pre>{html.escape(response.thinking)}</pre></details>'
            )

        parts.append(f'<div class="ai-answer">{html.escape(response.answer)}</div>')

        if include_sources and response.sources:
            parts.append('<section class="ai-sources"><h4>sources</h4><ol>')
            for s in response.sources:
                title = html.escape(s.title or s.link)
                link = html.escape(s.link)
                parts.append(f'<li><a href="{link}" target="_blank" rel="noopener">{title}</a></li>')
            parts.append("</ol></section>")

        parts.append("</article>")
        return "".join(parts)
