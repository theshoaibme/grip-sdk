# Grip Python SDK: User Guide

The **Grip Python SDK** (`grip`) enables effortless programmatic interaction with Grip AI Search, dynamic search providers, system rules, custom callable tools, and multi-turn sessions.

---

## 1. Installation

```bash
pip install grip-sdk
```

---

## 2. Quickstart

```python
import grip

client = grip.Grip()

# Execute AI search
response = client.search.query("Latest James Webb Space Telescope discoveries")
print(response.answer)

# Iterate grounded citations
for source in response.sources:
    print(f"- {source.title}: {source.link}")
```

---

## 3. Real-Time Token Streaming

```python
import grip

client = grip.Grip()

for chunk in client.search.stream("Explain gravitational waves"):
    if chunk.event == "delta":
        print(chunk.delta, end="", flush=True)
print()
```

---

## 4. Asynchronous Client (`AsyncGrip`)

```python
import asyncio
from grip import AsyncGrip

async def main():
    async with AsyncGrip() as client:
        response = await client.search.query("Artificial intelligence ethics")
        print(response.answer)

asyncio.run(main())
```

---

## 5. Multi-Turn Conversational Sessions

```python
session = client.sessions.create(title="Deep Dive Session")

# Turn 1
r1 = client.chat("What are superconductors?", session_id=session.session_id)
print(r1.answer)

# Turn 2 with retained context
r2 = client.chat("What is the Meissner effect in them?", session_id=session.session_id)
print(r2.answer)
```

---

## 6. System Rules & Personas

```python
client.rules.set_identity("You are a senior astrophysicist at NASA.")
client.rules.set_response_format("Concise bullet points with references.")
client.rules.add("Always cite peer-reviewed academic papers.")
```

---

## 7. Custom Callable Tools

```python
@client.tool(description="Convert currency from USD to EUR")
def convert_usd_to_eur(amount: float) -> float:
    return amount * 0.92

# Test tool execution
print(client.tools.call("convert_usd_to_eur", amount=100.0))
```
