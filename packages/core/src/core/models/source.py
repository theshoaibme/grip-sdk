"""Data models representing grounded web sources and references."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SourceItem:
    """A grounded web source cited in an AI search response."""

    url: str = ""
    title: str = ""
    snippet: str = ""
    domain: str = ""
    rank: int = 1

    def __init__(
        self,
        url: str = "",
        title: str = "",
        snippet: str = "",
        domain: str = "",
        rank: int = 1,
        link: str | None = None,
    ) -> None:
        self.url = url or link or ""
        self.title = title
        self.snippet = snippet
        self.domain = domain
        self.rank = rank

    @property
    def link(self) -> str:
        """Alias for url for backwards compatibility."""
        return self.url

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "link": self.url,
            "snippet": self.snippet,
            "domain": self.domain,
            "rank": self.rank,
        }
