"""Rate limiting middleware for API requests."""

from __future__ import annotations

import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from grip_engine.infrastructure.rate_limit import RateLimiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enforce rate limits per client IP."""

    def __init__(self, app, capacity: int = 60, refill_per_sec: float = 2.0) -> None:
        super().__init__(app)
        self.limiter = RateLimiter(capacity=capacity, refill_per_sec=refill_per_sec)

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip health check and root UI
        if request.url.path in ("/", "/health", "/docs", "/openapi.json"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()

        allowed = self.limiter.acquire(client_ip)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "message": "Rate limit exceeded. Please wait before retrying.",
                    "timestamp": time.time(),
                },
                headers={"Retry-After": "2"},
            )

        return await call_next(request)
