"""Multi-turn conversational session routes."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from ..dependencies import get_session_store
from ..schemas.requests import CreateSessionRequestSchema
from ..schemas.responses import SessionDetailSchema, SessionSummarySchema
from grip_engine.infrastructure.session_store import SessionStore

router = APIRouter(tags=["Sessions"])


@router.post("/api/v1/sessions", response_model=SessionDetailSchema)
@router.post("/sessions", response_model=SessionDetailSchema)
def create_session(
    payload: CreateSessionRequestSchema,
    store: SessionStore = Depends(get_session_store),
):
    """Create a new conversational session."""
    session = store.create_session(
        title=payload.title,
        session_id=payload.session_id,
        metadata=payload.metadata,
    )
    return session.to_dict()


@router.get("/api/v1/sessions")
@router.get("/sessions")
def list_sessions(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    store: SessionStore = Depends(get_session_store),
):
    """List stored conversational sessions."""
    sessions = store.list_sessions()
    paged = sessions[offset : offset + limit]
    return {
        "sessions": [s.to_dict() for s in paged],
        "total": len(sessions),
        "limit": limit,
        "offset": offset,
    }


@router.get("/api/v1/sessions/{session_id}")
@router.get("/sessions/{session_id}")
def get_session(
    session_id: str,
    store: SessionStore = Depends(get_session_store),
):
    """Retrieve session details and history."""
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return session.to_dict()


@router.delete("/api/v1/sessions/{session_id}")
@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    store: SessionStore = Depends(get_session_store),
):
    """Delete a session."""
    deleted = store.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return {"status": "success", "session_id": session_id}


@router.post("/api/v1/sessions/clear")
@router.post("/sessions/clear")
def clear_sessions(
    store: SessionStore = Depends(get_session_store),
):
    """Clear all stored sessions."""
    count = store.clear_all()
    return {"cleared": count, "status": "success"}
