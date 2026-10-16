"""Tests for Grip AI Agent, provider model resolution, PDF generation, and MCP connectivity."""

import os
import tempfile
import time
import pytest
import grip
from grip.agent import Agent, AgentResult, MCPClient, create_in_memory_mcp_client


def test_agent_provider_model_defaults():
    """Verify default model names are properly selected based on provider."""
    # Google defaults to gemini-2.5-flash
    google_agent = Agent(provider="google")
    assert google_agent.provider == "google"
    assert google_agent.model == "gemini-2.5-flash"

    # Specific Google model
    pro_agent = Agent(provider="google", model="gemini-2.5-pro")
    assert pro_agent.model == "gemini-2.5-pro"

    # OpenAI defaults to gpt-4o
    openai_agent = Agent(provider="openai")
    assert openai_agent.provider == "openai"
    assert openai_agent.model == "gpt-4o"

    # Grip defaults to grip-fast
    grip_agent = Agent(provider="grip")
    assert grip_agent.provider == "grip"
    assert grip_agent.model == "grip-fast"


def test_agent_built_in_tools_presence():
    """Verify agent comes with search, PDF generation, and safe utility tools."""
    agent = Agent(provider="google")
    tool_names = agent.tools.names()

    assert "web_search" in tool_names
    assert "create_pdf" in tool_names
    assert "calculator" in tool_names
    assert "page_fetcher" in tool_names
    assert "summarizer" in tool_names


def test_agent_create_pdf_tool():
    """Verify built-in create_pdf tool produces valid, well-structured PDF files."""
    agent = Agent(provider="google")
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        content = """# Executive Research Report
This document summarizes recent advancements in artificial intelligence.

## Section 1: Multimodal Reasoning
- Deep thinking traces
- Agentic tool invocation
- PDF and report publishing

## Section 2: Implementation Invariants
Grip SDK guarantees 100% self-contained Python compatibility without external dependencies.
"""
        res = agent.tools.call(
            "create_pdf",
            output_path=tmp_path,
            title="Grip AI Research Document",
            content=content,
            author="Grip Autonomous Agent",
        )

        assert res["success"] is True
        assert os.path.exists(tmp_path)
        assert os.path.getsize(tmp_path) > 500

        with open(tmp_path, "rb") as f:
            header = f.read(8)
            assert header.startswith(b"%PDF-1.")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_agent_custom_tool_decorator():
    """Verify registering custom python functions using @agent.tool decorator."""
    agent = Agent(provider="google")

    @agent.tool(description="Calculate portfolio ROI")
    def calculate_roi(initial: float, final: float) -> float:
        return round(((final - initial) / initial) * 100, 2)

    assert "calculate_roi" in agent.tools
    result = agent.tools.call("calculate_roi", initial=100.0, final=150.0)
    assert result == 50.0


def test_agent_mcp_tool_connection():
    """Verify Model Context Protocol (MCP) tool discovery and execution."""
    agent = Agent(provider="google")

    # In-memory mock MCP server advertising external tools
    mock_mcp = create_in_memory_mcp_client({
        "query_database": (
            "Query internal database for records",
            lambda table, limit=10: [{"id": 1, "table": table, "status": "active"}],
            {"type": "object", "properties": {"table": {"type": "string"}}, "required": ["table"]},
        ),
        "fetch_api_metrics": (
            "Fetch server latency and throughput",
            lambda: {"latency_ms": 12.4, "rps": 450},
            {"type": "object", "properties": {}},
        ),
    })

    # Connect MCP server to agent
    agent.connect_mcp(client=mock_mcp)

    assert "query_database" in agent.tools
    assert "fetch_api_metrics" in agent.tools

    db_res = agent.tools.call("query_database", table="users")
    assert db_res == [{"id": 1, "table": "users", "status": "active"}]

    metrics_res = agent.tools.call("fetch_api_metrics")
    assert metrics_res["latency_ms"] == 12.4

    agent.close()


def test_agent_run_with_pdf_creation():
    """Verify autonomous agent runs task and produces requested PDF output."""
    agent = Agent(provider="google", model="gemini-2.5-flash")
    target_pdf = os.path.join(tempfile.gettempdir(), f"quantum_report_{os.getpid()}_{time.time_ns()}.pdf")

    try:
        task = f"Explain the principles of quantum superposition and create a PDF at {target_pdf}"
        result = agent.run(task)

        assert isinstance(result, AgentResult)
        assert result.provider == "google"
        assert result.model == "gemini-2.5-flash"
        assert len(result.output) > 20
        assert target_pdf in result.files_created or os.path.exists(target_pdf)
        assert os.path.getsize(target_pdf) > 0
    finally:
        if os.path.exists(target_pdf):
            os.remove(target_pdf)


def test_grip_client_create_agent_shorthand():
    """Verify creating an agent from the primary Grip client."""
    client = grip.Grip()
    agent = client.create_agent(
        name="AnalystAgent",
        provider="google",
        model="gemini-2.5-flash",
        instructions="Analyze financial markets.",
    )

    assert isinstance(agent, Agent)
    assert agent.name == "AnalystAgent"
    assert agent.provider == "google"
    assert agent.model == "gemini-2.5-flash"
