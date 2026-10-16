"""Unit tests for response formatters."""

from core.models.response import SearchResponse, SourceItem
from grip_engine.formatters.base import FormatterRegistry


def test_formatters_markdown_and_json():
    registry = FormatterRegistry()
    response = SearchResponse(
        query="What is quantum mechanics?",
        answer="Quantum mechanics is a fundamental theory in physics.",
        sources=[
            SourceItem(title="Quantum Physics", url="https://example.com/physics"),
        ],
    )

    md = registry.format(response, format_name="markdown")
    assert "Quantum mechanics" in md
    assert "Quantum Physics" in md

    json_str = registry.format(response, format_name="json")
    assert "Quantum mechanics" in json_str
    assert "https://example.com/physics" in json_str


def test_formatters_citations_and_text():
    registry = FormatterRegistry()
    response = SearchResponse(
        query="Gravitational waves",
        answer="Ripples in spacetime.",
        sources=[
            SourceItem(title="LIGO Scientific Collaboration", url="https://ligo.org"),
        ],
    )

    citations = registry.format(response, format_name="citations", style="apa")
    assert "LIGO" in citations

    plain = registry.format(response, format_name="text")
    assert "Ripples in spacetime." in plain
