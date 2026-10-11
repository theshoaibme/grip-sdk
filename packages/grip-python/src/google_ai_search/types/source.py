"""Grounded web source citation models."""

from dataclasses import dataclass


@dataclass
class SourceItem:
    """A grounded web source citation returned by Google AI Search."""

    title: str
    link: str
    snippet: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "title": self.title,
            "link": self.link,
            "snippet": self.snippet,
        }
