# Grip SDK (`grip-sdk` / `grip`)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/Platform-Grip%20AI-black.svg)](https://grip.theshoaib.me/)

The official enterprise SDK, search orchestration engine, and microservices platform inspired by and built for [Grip](https://grip.theshoaib.me/) ("Grab anything on the web").

---

## 🚀 Key Features

- **Dynamic Multi-Provider AI Search**: Seamless runtime routing between Google AI Mode, OpenAI Search, and custom search providers.
- **Real-Time Token Streaming**: Server-Sent Events (SSE) token-by-token streaming with model reasoning (`thinking`).
- **Multi-Turn Conversational Sessions**: Persistent interactive input sessions with context history retention.
- **System Rules & Personas**: Granular control over assistant identity, response formatting, and negative constraints.
- **Agent Capabilities**: Built-in tools (calculator, unit converter, json extractor, etc.), strict planning, and workflows.
- **Modern Clean UI**: Zero-border dark ChatGPT-style interface.
- **Enterprise Architecture**: Monorepo split into core protocols (`grip-core`), high-level client SDK (`grip-python`), engine (`grip-engine`), REST/SSE API (`services/api`), and background worker (`services/worker`).

---

## 📦 Directory Structure

```text
grip-sdk/
│
├── packages/
│   ├── grip-core/          # Shared domain models, protocols, validation, errors, and config
│   │   ├── pyproject.toml
│   │   └── src/grip_core/
│   │
│   └── grip-python/        # Ergonomic Python Client SDK (sync & async, CLI)
│       ├── pyproject.toml
│       ├── src/grip/       # client.py, async_client.py, cli/, resources/, types/
│       └── tests/
│
├── engine/                 # Core search orchestration, dynamic provider registry, agent, formatters
│   ├── pyproject.toml
│   └── src/grip_engine/    # GripEngine, providers (Google, OpenAI), tools, formatters
│
├── services/
│   ├── api/                # FastAPI REST & real-time SSE streaming service
│   │   ├── pyproject.toml
│   │   └── app/            # routes/, schemas/, middleware/, templates/index.html
│   │
│   └── worker/             # Background task daemon for maintenance and queue processing
│       ├── pyproject.toml
│       └── app/
│
├── deploy/                 # Dockerfiles, docker compose, production nginx reverse proxy
├── tests/                  # Unit, Integration, and Security test suites
├── examples/               # basic_search.py, async_search.py
├── docs/                   # architecture.md, api.md, sdk.md, deployment.md
├── scripts/                # build.py, release_check.py
├── Makefile
├── pyproject.toml
└── LICENSE
```

---

## ⚡ Quickstart

### 1. Installation

```bash
pip install grip-sdk
```

Or from source:

```bash
make install
```

### 2. Synchronous Query

```python
import grip

client = grip.Grip()

# Basic search query
response = client.search.query("Latest breakthroughs in quantum computing")
print(response.answer)

# Grounded citations
for source in response.sources:
    print(f"- {source.title}: {source.link}")
```

### 3. Asynchronous Streaming

```python
import asyncio
from grip import AsyncGrip

async def main():
    async with AsyncGrip() as client:
        async for chunk in client.search.stream("Explain gravitational waves"):
            if chunk.event == "delta":
                print(chunk.delta, end="", flush=True)

asyncio.run(main())
```

### 4. Dynamic Provider Selection

```python
# Query via Google AI Mode
response = client.query("Tech news today", provider="google")

# Query via OpenAI provider
response = client.query("AI agents summary", provider="openai")
```

---

## 💻 CLI Commands

```bash
# AI Search in terminal
grip search "Who discovered penicillin?"

# Stream token-by-token
grip search "Explain photosynthesis"

# Interactive multi-turn chat
grip chat

# List active search providers
grip providers

# Run the local server and web UI
grip serve --port 8000
```

---

## 🧪 Testing & Build

```bash
# Run all tests
make test

# Run pre-release checks
make release-check

# Build package distributions
make build
```

---

## 📄 License

MIT © [Shoaib & Grip Contributors](https://grip.theshoaib.me/)