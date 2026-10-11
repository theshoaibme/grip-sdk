"""Pydantic response schemas for Grip API."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class SourceItemSchema(BaseModel):
    title: str = ""
    url: str = ""
    snippet: str = ""
    domain: str = ""
    rank: int = 1


class SearchResponseSchema(BaseModel):
    query: str
    answer: str
    sources: list[SourceItemSchema] = Field(default_factory=list)
    session_id: str | None = None
    thread_id: str | None = None
    suggestions: list[str] = Field(default_factory=list)
    thinking: str | None = None
    cached: bool = False
    provider: str = "grip"
    status: str = "success"
    search_time: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class HealthResponseSchema(BaseModel):
    status: str
    ready: bool
    reason: str
    service: str = "grip-platform"
    version: str = "0.3.0"
    active_providers: list[str] = Field(default_factory=list)


class SessionMessageSchema(BaseModel):
    role: str
    content: str
    timestamp: float
    sources: list[dict[str, Any]] = Field(default_factory=list)


class SessionDetailSchema(BaseModel):
    session_id: str
    title: str
    created_at: str | float
    updated_at: str | float
    messages: list[SessionMessageSchema] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionSummarySchema(BaseModel):
    session_id: str
    title: str
    message_count: int
    created_at: str | float
    updated_at: str | float
