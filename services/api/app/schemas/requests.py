"""Pydantic request schemas for Grip API."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class SearchRequestSchema(BaseModel):
    query: str = Field(..., min_length=1, description="The query string to search")
    session_id: str | None = Field(None, description="Optional multi-turn session ID")
    thread_id: str | None = Field(None, description="Optional thread identifier")
    provider: str = Field("google", description="AI search provider (google, openai, etc.)")
    timeout: float | None = Field(None, ge=1.0, le=300.0, description="Execution timeout in seconds")


class CreateSessionRequestSchema(BaseModel):
    title: str | None = Field(None, description="Title of the session")
    session_id: str | None = Field(None, description="Explicit custom session ID")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata dictionary")


class RuleRequestSchema(BaseModel):
    content: str = Field(..., min_length=1, description="Rule content or instruction")
    name: str | None = Field(None, description="Rule name")
    priority: int = Field(50, ge=1, le=100, description="Rule execution priority")
