# AGENTS.md — AI Agent Development Rules & Architecture Guidelines

> **Target Repository**: `grip-sdk` (`theshoaibme/grip-sdk`)  
> **Official Platform**: [Grip AI](https://grip.theshoaib.me/)  
> **Package Registry**: [PyPI: grip-sdk](https://pypi.org/project/grip-sdk/)  
> **Scope**: All AI coding agents (Antigravity, Cursor, Windsurf, GitHub Copilot, Codex, etc.) modifying or contributing to this repository MUST strictly adhere to these rules.

---

## 1. Project Purpose & Philosophy

`grip-sdk` is the official, high-performance developer library for **Grip AI**. It enables Python applications to integrate:
1. **Dynamic Multi-Provider AI Search** (Google AI Mode, OpenAI Search, Grip Native).
2. **Server-Sent Events (SSE) Token Streaming** with deep model reasoning (`thinking`).
3. **Conversational Multi-Turn Sessions** with memory and history retention.
4. **Agentic Capabilities** (custom tools, rules, skills, workflows, formatters).

**Core Philosophy**:
- **Pure SDK Library**: This repository is a clean, pip-installable Python SDK and client. Do **NOT** re-introduce microservice Docker deployment pipelines, `services/api`, or `services/worker`.
- **Zero-Friction Installation**: `pip install grip-sdk` must remain completely self-contained with minimal external dependencies.
- **Backwards Compatibility**: Never break existing public APIs (`grip.Grip`, `grip.AsyncGrip`, `client.search.query`, `client.search.stream`, `client.sessions`).

---

## 2. Monorepo Architecture & Invariants

```text
grip-sdk/
├── packages/
│   ├── grip-core/          # Shared domain models (Request, Response, Source, Session), validation, errors
│   │   ├── pyproject.toml
│   │   └── src/grip_core/
│   │
│   └── grip-python/        # Ergonomic Client SDK (Grip, AsyncGrip, CLI, resources, types)
│       ├── pyproject.toml
│       ├── README.md
│       └── src/grip/
│
├── engine/                 # Multi-provider orchestration engine (GripEngine, Google, OpenAI, Registry)
│   ├── pyproject.toml
│   └── src/grip_engine/
│
├── google_ai_search/       # Core browser automation engine and stealth search drivers
├── app/                    # Built-in local server and ChatGPT-style dark mode web UI
├── examples/               # Standalone runnable scripts (basic_search.py, async_search.py, test_server.py)
├── tests/                  # Unit, Integration, and Security test suites (must always pass 100%)
├── scripts/                # build.py, release_check.py
├── .github/workflows/      # ci.yml, build-and-release.yml
├── pyproject.toml          # Root package definition and pytest config
└── AGENTS.md               # This guideline specification
```

### Critical Package Bundling Rule
When packaging `packages/grip-python` for PyPI distributions:
- `packages/grip-python/src/` must contain `grip`, `grip_core`, and `grip_engine` so that `pip install grip-sdk` is 100% self-contained without requiring separate unreleased packages from PyPI.

---

## 3. Python Standards & Code Quality

1. **Python Version Compatibility**: Target Python `>=3.10` (tested across 3.10, 3.11, 3.12, 3.13).
2. **Type Annotations**:
   - Always use standard typing (`from __future__ import annotations`, `str | None`, `list[dict[str, Any]]`).
   - All public classes and functions must specify return types and parameter types.
3. **Error Handling**:
   - Raise typed exceptions defined in `grip_core.errors` (e.g. `ProviderError`, `ValidationError`, `SessionNotFoundError`).
   - Never raise bare exceptions or swallow errors silently.
4. **Docstrings & Comments**:
   - Maintain documentation integrity. Preserve all existing docstrings and architectural notes.
   - Any new public methods must have clear docstrings explaining inputs and return types.

---

## 4. Multi-Provider & Search Rules

1. **Dynamic Provider Dispatch**:
   - All search queries must route through `ProviderRegistry`.
   - Built-in providers: `"google"`, `"google_ai"`, `"grip"`, `"grip_ai"`, `"openai"`.
   - Never hardcode a single provider in `GripEngine.search()`.
2. **Streaming Protocol**:
   - Streaming must yield typed `StreamChunk` or dict objects containing:
     - `event: "thinking"` / `type: "thinking"` for reasoning.
     - `event: "delta"` / `type: "delta"` for token chunks.
     - `event: "done"` with `response` dictionary and grounded sources.
3. **Session Consistency**:
   - All multi-turn conversation sessions must preserve `session_id`, `created_at`, `updated_at`, and message turn history.

---

## 5. Testing & Verification Requirements

**Mandatory Verification Before Every Commit:**

Agents MUST execute and verify all tests before completing any coding task:

```bash
# 1. Run full test suite across the monorepo
.venv/bin/pytest tests/ packages/grip-python/tests/

# 2. Run release integrity check
.venv/bin/python scripts/release_check.py
```

- **Zero Test Failures**: Every pull request or commit must pass 100% of the tests (currently 35+ tests).
- **Graceful Imports**: Example scripts in `examples/` must include automatic `sys.path` bootstrapping so they run seamlessly in any environment.

---

## 6. Versioning & Release Checklist

When updating package versions:
1. **Synchronize Version Numbers** across all configuration files:
   - `packages/grip-python/src/grip/_version.py`
   - `packages/grip-python/pyproject.toml`
   - `pyproject.toml`
   - `packages/grip-core/pyproject.toml`
   - `engine/pyproject.toml`
2. **Verify Build**:
   ```bash
   .venv/bin/python scripts/build.py
   .venv/bin/twine check packages/grip-python/dist/*
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
