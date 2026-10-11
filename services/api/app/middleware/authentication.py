"""Authentication middleware for optional API key enforcement."""

from __future__ import annotations

import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Inspect optional Authorization bearer tokens."""

    def __init__(self, app, api_key: str | None = None) -> None:
        super().__init__(app)
        self.api_key = api_key or os.getenv("GRIP_API_KEY")

    async def dispatch(self, request: Request, call_next) -> Response:
        # If no server API key configured, pass through
        if not self.api_key:
            return await call_next(request)

        # Allow public UI, docs, and health
        if request.url.path in ("/", "/health", "/docs", "/openapi.json", "/favicon.ico"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        token = auth_header.removeprefix("Bearer ").strip() if auth_header.startswith("Bearer ") else request.headers.get("X-API-Key", "")

        if token != self.api_key:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Unauthorized",
                    "message": "Invalid or missing API key in Authorization header.",
                },
            )

        return await call_next(request)
