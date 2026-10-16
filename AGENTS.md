# AGENTS.md — AI Agent Development Rules & Architecture Guidelines

> **Target Repository**: `grip-sdk` (`theshoaibme/grip-sdk`)  
> **Official Platform**: [Grip AI](https://grip.theshoaib.me/)  
> **Package Registry**: [PyPI: grip-sdk](https://pypi.org/project/grip-sdk/)  
> **Scope**: All AI coding agents (Antigravity, Cursor, Windsurf, GitHub Copilot, Codex, etc.) modifying this repository MUST strictly adhere to these rules. In addition, Section 8 provides the official client developer guide for using rules across all autonomous AI agents.

---

## 1. Project Purpose & Philosophy

`grip-sdk` is the official, high-performance developer library for **Grip AI**. It enables Python applications to integrate:
1. **Dynamic Multi-Provider AI Search** (Google AI Mode, OpenAI Search, Grip Native).
2. **Server-Sent Events (SSE) Token Streaming** with deep model reasoning (`thinking`).
3. **Conversational Multi-Turn Sessions** with memory and history retention.
4. **Agentic Capabilities** (custom tools, rules, skills, workflows, formatters, PDF generation, and MCP).

### Core Philosophy
- **Pure SDK Library**: This repository is a clean, pip-installable Python SDK and client. Do **NOT** re-introduce microservice Docker deployment pipelines, `services/api`, or `services/worker`.
- **Zero-Friction Installation**: `pip install grip-sdk` must remain completely self-contained with minimal external dependencies.
- **Backwards Compatibility**: Never break existing public APIs (`grip.Grip`, `grip.AsyncGrip`, `client.search.query`, `client.search.stream`, `client.sessions`, `client.create_agent`).

---

## 2. Monorepo Architecture & Invariants

```text
grip-sdk/
├── packages/
│   ├── core/               # Shared domain models, protocols, validation, errors + browser search engine
│   │   ├── pyproject.toml      # distribution: core
│   │   └── src/
│   │       ├── core/               # import: core (models, protocols, validation, errors, config)
│   │       └── google_ai_search/   # import: google_ai_search (browser automation engine)
│   │
│   ├── engine/             # Multi-provider orchestration engine (GripEngine, Google, OpenAI, Registry)
│   │   ├── pyproject.toml      # distribution: grip-engine
│   │   └── src/grip_engine/
│   │
│   └── sdk/                # Ergonomic Client SDK (Grip, AsyncGrip, CLI, resources, types)
│       ├── pyproject.toml      # distribution: grip-sdk
│       ├── README.md
│       ├── src/grip/
│       └── src/                # generated vendored mirrors: core, google_ai_search, grip_engine
│
├── app/                    # Built-in local server and ChatGPT-style dark mode web UI
├── examples/               # Standalone runnable scripts (basic_search.py, async_search.py, test_server.py)
├── tests/                  # Unit, Integration, and Security test suites (must always pass 100%)
├── scripts/                # build.py, release_check.py, sync_vendored.py
├── .github/workflows/      # ci.yml, build-and-release.yml
├── package.json            # Bun task runner (dev, test, build, verify, sync, clean)
├── Makefile                # Thin aliases delegating to the Bun task runner
├── pyproject.toml          # Root tooling config (pytest pythonpath)
└── AGENTS.md               # This guideline specification
```

### Critical Package Bundling Invariant
When packaging `packages/sdk` for PyPI distributions:
- `packages/sdk/src/` must contain the vendored mirrors `core`, `google_ai_search`, and `grip_engine` so that `pip install grip-sdk` is 100% self-contained without requiring separate unreleased packages from PyPI.
- The mirrors under `packages/sdk/src/` are **generated** by `python scripts/sync_vendored.py` — never edit them by hand. CI runs `scripts/sync_vendored.py --check` and fails on drift.

---

## 3. Python Standards & Code Quality

1. **Python Version Compatibility**: Target Python `>=3.10` (tested across 3.10, 3.11, 3.12, 3.13).
2. **Type Annotations**:
   - Always use standard typing (`from __future__ import annotations`, `str | None`, `list[dict[str, Any]]`).
   - All public classes and functions must specify return types and parameter types.
3. **Error Handling**:
   - Raise typed exceptions defined in `core.errors` (e.g. `ProviderError`, `AuthenticationError`, `RateLimitError`, `NotFoundError`, `APITimeoutError`, `APIConnectionError`).
   - Never raise bare exceptions or swallow errors silently.
4. **Model Ergonomics**:
   - Response dataclasses (`SearchResponse`, `Metadata`, `SourceItem`, `SessionDetail`) must inherit from `DictAccessMixin` to provide dual access: `res.answer` and `res["answer"]`.
5. **Docstrings & Comments**:
   - Maintain documentation integrity. Preserve all existing docstrings and architectural notes.
   - Any new public methods must have clear docstrings explaining inputs and return types.

---

## 4. Multi-Provider & Search Rules

1. **Dynamic Provider Dispatch**:
   - All search queries must route through `ProviderRegistry`.
   - Built-in providers: `"google"`, `"google_ai"`, `"grip"`, `"grip_ai"`, `"openai"`, `"chatgpt_web"`, `"gemini_web"`.
   - Never hardcode a single provider in `GripEngine.search()`.
2. **Multi-Provider Fallback Failover**:
   - `client.query()` and `client.stream()` must support `fallback` parameters (e.g. `fallback=["openai", "gemini_web"]`).
   - If the primary provider fails, automatically failover to fallback providers sequentially.
3. **Streaming Protocol**:
   - Streaming must yield typed `StreamChunk` or dict objects containing:
     - `event: "thinking"` / `type: "thinking"` for reasoning.
     - `event: "delta"` / `type: "delta"` for token chunks.
     - `event: "done"` with `response` dictionary and grounded sources.
   - `AsyncGrip.stream()` must yield chunks in real time without buffering the stream into memory.
4. **Session Consistency**:
   - All multi-turn conversation sessions must preserve `session_id`, `created_at`, `updated_at`, and message turn history.

---

## 5. Mandatory Verification Before Every Commit

Agents MUST execute and verify all checks before completing any coding task:

```bash
# 1. Run full test suite across the monorepo (70+ tests)
.venv/bin/pytest tests/ packages/sdk/tests/

# 2. Run release integrity check
.venv/bin/python scripts/release_check.py

# 3. Verify vendored mirrors have not drifted
.venv/bin/python scripts/sync_vendored.py --check
```

> Equivalent Bun tasks: `bun run test`, `bun run verify`, `bun run sync:check` (or `make test` / `make verify` / `make sync-check`).

- **Zero Test Failures**: Every pull request or commit must pass 100% of the tests.
- **Graceful Imports**: Example scripts in `examples/` must include automatic `sys.path` bootstrapping so they run seamlessly in any environment.

---

## 6. Versioning & Release Checklist

When updating package versions:
1. **Synchronize Version Numbers** across all configuration files:
   - `packages/sdk/src/grip/_version.py`
   - `packages/sdk/pyproject.toml`
   - `packages/core/src/core/__init__.py`
   - `packages/core/pyproject.toml`
   - `packages/engine/src/grip_engine/__init__.py`
   - `packages/engine/pyproject.toml`
2. **Verify Distribution Packages**:
   ```bash
   .venv/bin/python scripts/build.py
   .venv/bin/twine check packages/sdk/dist/*
   ```
3. **Git Tagging**:
   - Version tags MUST follow semantic versioning prefixed with `v` (e.g., `v0.3.5`).
   - Pushing tags triggers the [`.github/workflows/build-and-release.yml`](.github/workflows/build-and-release.yml) GitHub Actions workflow.

---

## 7. Prohibited Actions for Agents

❌ **DO NOT** recreate Docker container deploy workflows (`docker-deploy.yml`) or push container images to GitHub Packages.  
❌ **DO NOT** delete or compromise the dynamic multi-provider registry in `grip_engine`.  
❌ **DO NOT** remove or break the CLI entry points (`grip search`, `grip chat`, `grip providers`).  
❌ **DO NOT** commit untested code or bypass CI test suite checks.  
❌ **DO NOT** delete the root `README.md` user guides or add confusing multi-level folder tree ASCII diagrams back to the user documentation.

---

## 8. How to Use Rules for All Agents (Client & Developer Guide)

Grip SDK provides a unified, **provider-agnostic Agent Rules Engine** (`client.rules` and `agent.rules`). This allows clients to define strict behavioral guidelines, negative constraints, system personas, and output format specifications that apply seamlessly across **any agent provider** (`google`, `openai`, `chatgpt_web`, `gemini_web`, `grip`).

### 8.1 Core Concepts

| Concept | Purpose | Method |
|---|---|---|
| **System Identity** | Sets persona, role, and domain expertise | `client.rules.set_identity(...)` |
| **Response Format** | Mandates exact output structure (JSON, Markdown, citations) | `client.rules.set_response_format(...)` |
| **Behavioral Rules** | Explicit positive guidelines and negative constraints | `client.rules.add(...)` or `agent.add_rule(...)` |
| **Rule Priority** | Controls instruction precedence (1 = highest priority) | `priority=1` |
| **Active Toggling** | Dynamically enable or disable rules at runtime | `client.rules.toggle(name, active=...)` |
| **Prompt Compilation** | Formats rules into structured prompt directives | `client.rules.compile()` |

---

### 8.2 Global Client Rules (Inherited by All Agents)

Rules registered on `client.rules` are **globally inherited** by all agents instantiated via `client.create_agent()` or `client.agent()`.

```python
import grip

client = grip.Grip()

# 1. Define global system persona
client.rules.set_identity("You are a principal research scientist and AI governance auditor.")

# 2. Define global response formatting
client.rules.set_response_format(
    "Format answers with clear Markdown headers, bullet points, and explicit reference links."
)

# 3. Add global behavioral rules and negative constraints
client.rules.add(
    "Always verify claims against primary documentation or live web search.",
    name="fact_check",
    priority=1,
)
client.rules.add(
    "Never speculate on financial outcomes or provide unauthorized investment advice.",
    name="no_financial_advice",
    priority=1,
)
client.rules.add(
    "Keep final executive summaries under 300 words.",
    name="concise_summary",
    priority=2,
)

# Any agent created by the client automatically inherits these rules!
agent = client.create_agent(
    name="AuditorAgent",
    provider="google",  # or "openai", "grip", "chatgpt_web"
)
```

---

### 8.3 Agent-Level Rules (Customized Per Agent)

In addition to client-level rules, individual agents can declare their own specialized rules using `rules=[...]` at creation or dynamically via `agent.add_rule()`:

```python
import grip

client = grip.Grip()

# Create agent with dedicated rules
agent = client.create_agent(
    name="BiotechAgent",
    provider="google",
    instructions="Analyze clinical trials and drug interactions.",
    rules=[
        "Always cite peer-reviewed DOI links for biochemical claims.",
        "Never disclose unpublished trial participant identifiers.",
    ],
)

# Dynamically attach another rule
agent.add_rule(
    "Highlight FDA approval phase status in bold brackets (e.g. [Phase III]).",
    name="highlight_fda_phase",
    priority=1,
)

# Run the agent with rules automatically enforced
result = agent.run("Summarize latest Phase III oncology trials from 2026.")
print(result.output)
```

---

### 8.4 Multi-Provider Uniformity

The Rules Engine operates at the orchestration layer, ensuring that behavioral rules work identically regardless of which model or provider powers the agent:

```python
import grip

client = grip.Grip()
client.rules.set_identity("Senior Security Researcher")
client.rules.add("Strictly refuse to generate weaponized exploit payloads.", priority=1)
client.rules.set_response_format("Output strictly valid JSON with keys: 'vulnerability', 'severity', 'remediation'.")

# 1. Google Gemini-powered Agent
gemini_agent = client.create_agent(provider="google", model="gemini-2.5-flash")

# 2. OpenAI GPT-powered Agent
openai_agent = client.create_agent(provider="openai", model="gpt-4o")

# 3. Web AI Agent (Zero-API-key Browser Automation)
web_agent = client.create_agent(provider="chatgpt_web")

# All three agents strictly adhere to the same compiled rules!
```

---

### 8.5 Inspecting and Managing Rules at Runtime

```python
# List all active rules ordered by priority
active_rules = client.rules.list(active_only=True)
for r in active_rules:
    print(f"[{r.priority}] {r.name}: {r.content}")

# Temporarily disable a rule without deleting it
client.rules.toggle("concise_summary", active=False)

# Update an existing rule
client.rules.update("fact_check", priority=1, content="Mandatory live web search verification.")

# Inspect the compiled prompt directive block
print(client.rules.compile())

# Reset or clear all rules
client.rules.reset()
```

### 8.6 Compiled Rule Injection Format

When `agent.run(task)` executes, `self.rules.compile()` formats active directives into a standardized system prompt block:

```text
[SYSTEM IDENTITY]
You are a principal research scientist and AI governance auditor.

[RESPONSE FORMAT INSTRUCTIONS]
Format answers with clear Markdown headers, bullet points, and explicit reference links.

[STRICT BEHAVIORAL RULES]
1. Always verify claims against primary documentation or live web search.
2. Never speculate on financial outcomes or provide unauthorized investment advice.
3. Keep final executive summaries under 300 words.
```

This ensures maximum model compliance across reasoning loops, tool invocations, and output synthesis.
