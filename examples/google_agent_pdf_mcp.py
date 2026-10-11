#!/usr/bin/env python3
"""Grip AI Agent Example: Google Provider, PDF Generation, and MCP Tools.

Demonstrates:
1. Creating an autonomous Agent with provider 'google' and model 'gemini-2.5-flash'
2. Connecting custom tools with @agent.tool decorator
3. Connecting Model Context Protocol (MCP) servers
4. Generating formatted PDF reports from synthesized research
5. Running the agent end-to-end
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure local monorepo packages are discoverable
_ROOT = Path(__file__).resolve().parent.parent
for _p in [
    _ROOT / "packages" / "grip-python" / "src",
    _ROOT / "packages" / "grip-core" / "src",
    _ROOT / "engine" / "src",
    _ROOT,
]:
    _p_str = str(_p)
    if _p.exists() and _p_str not in sys.path:
        sys.path.insert(0, _p_str)

import grip
from grip.agent import Agent, create_in_memory_mcp_client


def main() -> None:
    print("=" * 65)
    print("🚀 Grip AI Autonomous Agent Demo")
    print("=" * 65)

    # 1. Initialize Agent with Provider 'google' and model 'gemini-2.5-flash'
    # Default model is automatically resolved to 'gemini-2.5-flash' for Google
    agent = grip.Agent(
        name="ResearchAndPublishAgent",
        provider="google",
        model="gemini-2.5-flash",
        instructions=(
            "You are an autonomous research intelligence agent. "
            "You analyze scientific questions, verify claims, invoke connected tools and MCP servers, "
            "and publish comprehensive PDF reports."
        ),
    )

    print(f"✓ Agent Name:     {agent.name}")
    print(f"✓ Provider:       {agent.provider}")
    print(f"✓ Model Name:     {agent.model}")
    print(f"✓ Built-in Tools: {agent.tools.names()}\n")

    # 2. Connect a custom Python Tool via decorator
    @agent.tool(description="Calculate quantum coherence time given dephasing rates")
    def calculate_coherence_time(gamma_1: float, gamma_2: float) -> dict[str, float]:
        t1 = round(1.0 / gamma_1, 2) if gamma_1 > 0 else 0.0
        t2 = round(1.0 / (0.5 * gamma_1 + gamma_2), 2) if (0.5 * gamma_1 + gamma_2) > 0 else 0.0
        return {"t1_relaxation_us": t1, "t2_dephasing_us": t2}

    print("✓ Registered custom tool: calculate_coherence_time")

    # 3. Connect a Model Context Protocol (MCP) server
    # We use an in-memory MCP server client for zero-dependency demonstration
    # (or connect via stdio: agent.connect_mcp(command="npx", args=["-y", "@modelcontextprotocol/server-..."]))
    mcp_server = create_in_memory_mcp_client({
        "fetch_arxiv_abstract": (
            "Retrieve ArXiv quantum mechanics research abstract",
            lambda paper_id: f"Paper {paper_id}: Quantum supremacy demonstrated through superconducting qubits with 99.8% fidelity.",
            {"type": "object", "properties": {"paper_id": {"type": "string"}}, "required": ["paper_id"]},
        ),
        "verify_institution_credential": (
            "Check academic affiliation and peer review record",
            lambda institution: {"institution": institution, "verified": True, "tier": "R1 Research"},
            {"type": "object", "properties": {"institution": {"type": "string"}}, "required": ["institution"]},
        ),
    })

    agent.connect_mcp(client=mcp_server)
    print(f"✓ Connected MCP Server. Active Agent Tools: {agent.tools.names()}\n")

    # 4. Execute Autonomous Task requesting PDF publication
    output_pdf = "/tmp/quantum_research_report.pdf"
    task = (
        f"Investigate quantum superposition and coherence times. "
        f"Fetch ArXiv data via MCP, compute coherence metrics, and publish a PDF report to {output_pdf}"
    )

    print(f"▶ Running Agent Task: '{task}'...\n")
    result = agent.run(task)

    # 5. Display Results
    print("=" * 65)
    print("📋 Agent Execution Results")
    print("=" * 65)
    print(f"Status:         {result.status}")
    print(f"Provider:       {result.provider}")
    print(f"Model:          {result.model}")
    print(f"Execution Time: {round(result.execution_time, 3)}s")
    print(f"Tools Called:   {result.tools_called}")
    print(f"Files Created:  {result.files_created}")
    print("\n--- Agent Final Answer ---")
    print(result.output)
    print("---------------------------\n")

    if os.path.exists(output_pdf):
        size = os.path.getsize(output_pdf)
        print(f"📄 Successfully created PDF: {output_pdf} ({size} bytes)")
    else:
        print(f"⚠️ PDF created at alternative location: {result.files_created}")

    agent.close()


if __name__ == "__main__":
    main()
