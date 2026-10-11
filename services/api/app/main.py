"""FastAPI entrypoint for Grip Platform API service."""

from __future__ import annotations

import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from .lifespan import lifespan
from .middleware.authentication import AuthenticationMiddleware
from .middleware.rate_limit import RateLimitMiddleware
from .middleware.request_id import RequestIdMiddleware
from .routes.health import router as health_router
from .routes.search import router as search_router
from .routes.sessions import router as sessions_router

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

app = FastAPI(
    title="Grip Platform",
    description="Enterprise Multi-Provider AI Search & Agent Orchestration API (https://grip.theshoaib.me/)",
    version="0.3.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Middlewares
app.add_middleware(AuthenticationMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestIdMiddleware)

# Include Routers
app.include_router(health_router)
app.include_router(search_router)
app.include_router(sessions_router)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def serve_ui():
    """Serve the clean Grip AI web interface."""
    index_file = TEMPLATES_DIR / "index.html"
    if index_file.exists():
        content = index_file.read_text(encoding="utf-8")
        port = os.getenv("PORT", "8000")
        content = content.replace("{{ port }}", port)
        return HTMLResponse(content)
    return HTMLResponse("<h1>Grip Platform API Running</h1>")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("services.api.app.main:app", host="0.0.0.0", port=port, reload=True)
