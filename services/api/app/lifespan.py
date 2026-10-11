"""Lifespan context manager for startup and shutdown lifecycle."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI

from grip_core.config import load_config
from grip_engine.engine import GripEngine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown events."""
    config = load_config()
    engine = GripEngine(config=config)
    app.state.config = config
    app.state.engine = engine
    app.state.session_store = engine.session_store

    yield

    # Clean up on shutdown if needed
    if hasattr(engine, "close"):
        engine.close()
