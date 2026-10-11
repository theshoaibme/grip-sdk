# Grip Platform: API Documentation

The Grip API service provides REST and Server-Sent Events (SSE) endpoints for AI searches, real-time streaming, and conversational sessions.

Interactive OpenAPI documentation is available at `http://localhost:8000/docs` or `http://localhost:8000/redoc`.

---

## 1. Health & Readiness

### `GET /health`
Returns the operational health and list of active AI search providers.

**Response `200 OK`**:
```json
{
  "status": "healthy",
  "ready": true,
  "reason": "Google AI search engine is ready",
  "service": "grip-platform",
  "version": "0.3.0",
  "active_providers": ["google", "openai"]
}
```

### `GET /health/ready`
Liveness/readiness probe for container orchestrators.

---

## 2. AI Search

### `POST /api/v1/search` (also `/search`)
Synchronous search query returning synthesized answer with grounded citations.

**Request Body**:
```json
{
  "query": "Quantum computing advances",
  "provider": "google",
  "session_id": "optional-session-id",
  "timeout": 60.0
}
```

**Response `200 OK`**:
```json
{
  "query": "Quantum computing advances",
  "answer": "Recent breakthroughs include error-corrected qubits...",
  "sources": [
    {
      "title": "Nature Physics",
      "url": "https://nature.com/articles/...",
      "snippet": "Demonstration of fault-tolerant quantum error correction...",
      "domain": "nature.com",
      "rank": 1
    }
  ],
  "thinking": "Synthesizing developments from Nature and IBM Quantum...",
  "status": "success",
  "provider": "google",
  "search_time": 2.14,
  "session_id": null
}
```

---

## 3. Real-Time Token Streaming

### `POST /api/v1/search/stream` (also `/search/stream`)
Server-Sent Events (SSE) stream returning token deltas in real-time.

**Request Body**:
```json
{
  "query": "Explain general relativity",
  "provider": "google"
}
```

**SSE Stream Output**:
```
event: delta
data: {"event": "delta", "delta": "General ", "text": "General "}

event: delta
data: {"event": "delta", "delta": "relativity ", "text": "relativity "}

event: done
data: {"event": "done", "response": { ... }}
```

---

## 4. Multi-Turn Sessions

- `POST /api/v1/sessions`: Create new session (`{"title": "Research"}`)
- `GET /api/v1/sessions`: List active sessions
- `GET /api/v1/sessions/{session_id}`: Retrieve session detail and messages
- `DELETE /api/v1/sessions/{session_id}`: Delete session
- `POST /api/v1/sessions/clear`: Clear all stored sessions
