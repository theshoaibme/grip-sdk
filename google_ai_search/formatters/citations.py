"""Citation formatters supporting APA, BibTeX, Chicago, and Markdown Footnote styles."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

if TYPE_CHECKING:
    from ..types.response import SearchResponse


class CitationFormatter:
    """Format grounded sources into scholarly citation standards."""

    def format(
        self,
        response: SearchResponse,
        style: str = "apa",
        **kwargs: Any,
    ) -> str:
        style_norm = style.lower().strip()
        if style_norm == "bibtex":
            return self._format_bibtex(response)
        if style_norm in ("footnote", "footnotes"):
            return self._format_footnotes(response)
        if style_norm == "chicago":
            return self._format_chicago(response)
        return self._format_apa(response)

    def _format_apa(self, response: SearchResponse) -> str:
        lines: list[str] = []
        for s in response.sources:
            domain = urlparse(s.link).netloc.replace("www.", "") or "Web Source"
            title = s.title.strip() if s.title else domain
            lines.append(f"{domain}. (n.d.). {title}. Retrieved from {s.link}")
        return "\n".join(lines)

    def _format_bibtex(self, response: SearchResponse) -> str:
        entries: list[str] = []
        for idx, s in enumerate(response.sources, start=1):
            domain = urlparse(s.link).netloc.replace("www.", "")
            key = re.sub(r"[^a-zA-Z0-9]", "", domain)[:12] + f"_{idx}"
            title = s.title.strip() if s.title else domain
            entry = (
                f"@misc{{{key},\n"
                f"  title = {{{{{title}}}}},\n"
                f"  howpublished = {{\\url{{{s.link}}}}},\n"
                f"  note = {{Accessed via Google AI Search}}\n"
                f"}}"
            )
            entries.append(entry)
        return "\n\n".join(entries)

    def _format_chicago(self, response: SearchResponse) -> str:
        lines: list[str] = []
        for s in response.sources:
            domain = urlparse(s.link).netloc.replace("www.", "")
            title = s.title.strip() if s.title else domain
            lines.append(f'"{title}." {domain}. Accessed via Google AI Search. {s.link}.')
        return "\n".join(lines)

    def _format_footnotes(self, response: SearchResponse) -> str:
        lines: list[str] = []
        for idx, s in enumerate(response.sources, start=1):
            title = s.title.strip() if s.title else s.link
            lines.append(f"[^{idx}]: [{title}]({s.link})")
        return "\n".join(lines)
