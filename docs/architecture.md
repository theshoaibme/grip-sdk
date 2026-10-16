# Grip Platform: Architecture Documentation

The **Grip Platform** (inspired by and built for [grip.theshoaib.me](https://grip.theshoaib.me/)) is designed as an enterprise-grade monorepo platform architecture composed of decoupled packages and services.

```
grip-sdk/
│
├── packages/
│   ├── core/               # Shared domain models, protocols, validation, errors, and config
│   │   └── src/
│   │       ├── core/               # import: core
│   │       └── google_ai_search/   # browser automation engine and stealth search drivers
│   ├── engine/             # Search orchestration, dynamic provider registry, agent, formatters
│   │   └── src/grip_engine/
│   └── sdk/                # Ergonomic Python Client SDK (sync & async, CLI)
│       └── src/grip/
│
├── app/                    # Built-in local Flask server and ChatGPT-style dark mode web UI
├── tests/                  # Unit, Integration, and Security test suites
├── examples/               # End-to-end runnable Python examples
├── scripts/                # build.py, release_check.py, sync_vendored.py
└── docs/                   # Platform, API, SDK, and deployment specifications
```

---

## 1. Dynamic Provider Architecture

To handle present and future AI search engines (Google AI Mode, OpenAI Search / Web Browsing, Perplexity, Claude, etc.), Grip uses a **Dynamic Provider Registry** pattern:

```
                  ┌────────────────────────┐
                  │      GripClient /      │
                  │      FastAPI / CLI     │
                  └───────────┬────────────┘
                              │
                              ▼
                  ┌────────────────────────┐
                  │       GripEngine       │
                  └───────────┬────────────┘
                              │
                              ▼
                  ┌────────────────────────┐
                  │    ProviderRegistry    │
                  └─────┬────────────┬─────┘
                        │            │
            ┌───────────▼──┐      ┌──▼───────────┐
            │ GoogleSearch │      │ OpenAISearch │  ... [Future Providers]
            └──────────────┘      └──────────────┘
```

### Adding New Search Providers
All providers implement the `BaseSearchProvider` abstract base class (`grip_engine.providers.base`):

```python
from grip_engine.providers.base import BaseSearchProvider
from core.models.response import SearchResponse, StreamChunk

class PerplexityProvider(BaseSearchProvider):
    def __init__(self, api_key: str | None = None):
        super().__init__(name="perplexity")
        self.api_key = api_key

    def ready(self) -> tuple[bool, str]:
        return bool(self.api_key), "Ready"

    def search(self, query: str, **kwargs) -> SearchResponse:
        ...

    def stream_search(self, query: str, **kwargs):
        ...
```

Register dynamically at runtime with:
```python
engine.register_provider("perplexity", PerplexityProvider(api_key="..."))
# Or set as default
engine.register_provider("perplexity", PerplexityProvider(api_key="..."), is_default=True)
```

---

## 2. Package Roles

- **`core`**: Defines standard data contracts (`SearchResponse`, `StreamChunk`, `SourceItem`, `SessionDetail`), security validators (`validate_query`, `validate_session_id`), and exceptions. It also ships the `google_ai_search` browser automation engine.
- **`grip-sdk`** (`packages/sdk`): Exposes the high-level `Grip` (sync) and `AsyncGrip` (async) client interfaces with interactive CLI (`grip search`, `grip chat`, `grip providers`, `grip serve`).
- **`grip-engine`**: Houses the multi-provider orchestrator, tool registry, system rules, strict planner, workflow pipelines, and response formatters.
