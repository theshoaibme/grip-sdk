# Grip Platform: Architecture Documentation

The **Grip Platform** (inspired by and built for [grip.theshoaib.me](https://grip.theshoaib.me/)) is designed as an enterprise-grade monorepo platform architecture composed of decoupled packages and services.

```
grip-platform/
│
├── packages/
│   ├── grip-core/          # Shared domain models, protocols, validation, errors, and config
│   └── grip-python/        # Ergonomic Python Client SDK (sync & async, CLI)
│
├── engine/                 # Search orchestration, dynamic provider registry, agent, formatters
│
├── services/
│   ├── api/                # FastAPI HTTP REST & real-time SSE streaming service
│   └── worker/             # Background task daemon for queue processing & session maintenance
│
├── deploy/                 # Dockerfiles, Docker Compose, Nginx reverse proxy
├── tests/                  # Unit, Integration, and Security test suites
├── examples/               # End-to-end runnable Python examples
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
from grip_core.models.response import SearchResponse, StreamChunk

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

- **`grip-core`**: Defines standard data contracts (`SearchResponse`, `StreamChunk`, `SourceItem`, `SessionDetail`), security validators (`validate_query`, `validate_session_id`), and exceptions.
- **`grip-python`**: Exposes the high-level `Grip` (sync) and `AsyncGrip` (async) client interfaces with interactive CLI (`grip search`, `grip chat`, `grip providers`, `grip serve`).
- **`grip-engine`**: Houses the multi-provider orchestrator, tool registry, system rules, strict planner, workflow pipelines, and response formatters.
- **`services/api`**: Exposes the high-performance FastAPI service with CORS, request ID tracing, rate limiting, and SSE streaming.
- **`services/worker`**: Runs background tasks and maintenance routines.
