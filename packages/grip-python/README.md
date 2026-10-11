# grip-sdk

Official Python SDK for Grip Platform (https://grip.theshoaib.me/).

## Installation

```bash
pip install grip-sdk
```

## Quickstart

```python
import grip

client = grip.Client()
response = client.query("Quantum computing breakthroughs")
print(response.answer)
```
