"""FastAPI request dependencies."""

from __future__ import annotations

from fastapi import Request
from grip_core.config import GripConfig
from grip_engine.engine import GripEngine
from grip_engine.infrastructure.session_store import SessionStore


def get_engine(request: Request) -> GripEngine:
    return request.app.state.engine


def get_config(request: Request) -> GripConfig:
    return request.app.state.config


def get_session_store(request: Request) -> SessionStore:
    return request.app.state.session_store
