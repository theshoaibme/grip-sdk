# Grip SDK (`grip-sdk`)

[![PyPI Version](https://img.shields.io/pypi/v/grip-sdk.svg?color=blue)](https://pypi.org/project/grip-sdk/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![CI Pipeline](https://github.com/theshoaibme/grip-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/theshoaibme/grip-sdk/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Grip%20AI-6366f1.svg)](https://grip.theshoaib.me/)

The official developer SDK for **[Grip AI](https://grip.theshoaib.me/)**. Integrate lightning-fast AI Search, real-time token streaming, deep model reasoning, and multi-turn conversational agents into any Python application with a simple, ergonomic interface.

---

## ⚡ Installation

Install the official package from PyPI:

```bash
pip install grip-sdk
```

---

## 🚀 How to Use

### 1. Basic AI Search

```python
from grip import Grip

client = Grip()

# Ask any query
response = client.query("What are the latest breakthroughs in fusion energy?")

print(response.answer)

# View grounded sources and citations
for source in response.sources:
    print(f"- {source.title}: {source.link or source.url}")
```

---

### 2. Live Token Streaming (SSE)

Stream responses token-by-token with instant terminal or UI rendering:

```python
from grip import Grip

client = Grip()

for chunk in client.stream("Explain gravitational time dilation simply"):
    # Live thinking process
    if chunk.event == "thinking" and chunk.thinking:
        print(f"\n[Reasoning]: {chunk.thinking}\n")
    # Content tokens
    elif chunk.event == "delta" and chunk.delta:
        print(chunk.delta, end="", flush=True)

print()
```

---

### 3. Asynchronous Streaming (`AsyncGrip`)

Ideal for FastAPI, asyncio, Discord bots, and modern async web frameworks:

```python
import asyncio
from grip import AsyncGrip

async def main():
    async with AsyncGrip() as client:
        async for chunk in client.stream("Summary of quantum error correction"):
            if chunk.event == "delta" and chunk.delta:
                print(chunk.delta, end="", flush=True)
    print()

asyncio.run(main())
```

---

### 4. Multi-Turn Conversational Sessions

Persist context across multiple questions:

```python
from grip import Grip

client = Grip()

# Create a conversation session
session = client.sessions.create(title="Astrophysics Discussion")

# First question
res1 = client.chat("What is the event horizon of a black hole?", session_id=session.session_id)
print(res1.answer)

# Follow-up with retained conversational memory
res2 = client.chat("Can anything escape it once inside?", session_id=session.session_id)
print(res2.answer)
```

---

### 5. Multi-Provider Routing

Switch between search providers dynamically at runtime:

```python
from grip import Grip

client = Grip()

# Query Google AI Search
google_res = client.query("Recent AI news", provider="google")

# Query OpenAI Search
openai_res = client.query("Recent AI news", provider="openai")

# Query Grip Native Engine
grip_res = client.query("Recent AI news", provider="grip")
```

---

## 💻 Command Line Interface (CLI)

`grip-sdk` includes an interactive CLI available directly in your terminal:

```bash
# Instant search from your terminal
grip search "Who discovered Penicillin?"

# Stream answer token-by-token
grip search "Explain superconductivity"

# Launch an interactive multi-turn chat session
grip chat

# List all registered search providers
grip providers

# Inspect version
grip --version
```

---

## 🧪 Interactive Web Playground

Launch the visual test server with a ChatGPT-style dark mode interface:

```bash
python examples/test_server.py
```

Then open **http://127.0.0.1:8080** in your browser to test live streaming, thinking reasoning blocks, and conversational sessions interactively.

---

## ⚙️ Configuration

Grip SDK works out of the box with zero configuration. You can customize behavior using environment variables or code:

| Variable | Description | Default |
| :--- | :--- | :--- |
| `GRIP_API_URL` | Remote Grip Platform API endpoint | `http://127.0.0.1:8000` |
| `GRIP_API_KEY` | Optional API key for authenticated gateways | `None` |
| `GRIP_DEFAULT_PROVIDER` | Default AI search provider (`google`, `openai`, `grip`) | `google` |
| `OPENAI_API_KEY` | Required only when using `provider="openai"` | `None` |

```python
from grip import Grip

# Custom client configuration
client = Grip(
    base_url="https://grip.theshoaib.me",
    api_key="your_api_key",
    provider="google",
    timeout=30.0,
)
```

---

## 📄 License

MIT © [Grip AI Platform](https://grip.theshoaib.me/)