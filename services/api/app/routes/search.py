"""Search and AI streaming routes."""

from __future__ import annotations

import json
from typing import AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from ..dependencies import get_engine
from ..schemas.requests import SearchRequestSchema
from ..schemas.responses import SearchResponseSchema
from grip_engine.engine import GripEngine

router = APIRouter(tags=["Search"])


@router.post("/api/v1/search", response_model=SearchResponseSchema)
@router.post("/search", response_model=SearchResponseSchema)
@router.post("/ai-search", response_model=SearchResponseSchema)
@router.post("/answer", response_model=SearchResponseSchema)
def search_query(
    payload: SearchRequestSchema,
    engine: GripEngine = Depends(get_engine),
):
    """Execute synchronous AI search query."""
    try:
        res = engine.search(
            query=payload.query,
            session_id=payload.session_id,
            thread_id=payload.thread_id,
            provider=payload.provider,
        )
        return res.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/v1/search/stream")
@router.post("/search/stream")
@router.post("/ai-search/stream")
def search_stream(
    payload: SearchRequestSchema,
    engine: GripEngine = Depends(get_engine),
):
    """Real-time SSE token-by-token streaming endpoint."""
    def event_stream():
        try:
            for chunk in engine.stream_search(
                query=payload.query,
                session_id=payload.session_id,
                thread_id=payload.thread_id,
                provider=payload.provider,
            ):
                cdata = chunk.to_dict() if hasattr(chunk, "to_dict") else chunk
                event_type = cdata.get("event") or cdata.get("type") or "delta"
                yield f"event: {event_type}\ndata: {json.dumps(cdata)}\n\n"
        except Exception as exc:
            err_data = {"event": "error", "message": str(exc), "status": 500}
            yield f"event: error\ndata: {json.dumps(err_data)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/v1/providers")
def list_providers(engine: GripEngine = Depends(get_engine)):
    """List dynamically registered search providers."""
    return {"providers": engine.registry.list_providers(), "default": engine.name}
