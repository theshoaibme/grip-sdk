"""Health check routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from ..dependencies import get_engine
from ..schemas.responses import HealthResponseSchema
from grip_engine.engine import GripEngine

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponseSchema)
def health_check(engine: GripEngine = Depends(get_engine)):
    """Health check endpoint verifying provider readiness."""
    ready, reason = engine.ready()
    providers = engine.registry.list_providers()
    return HealthResponseSchema(
        status="healthy" if ready else "degraded",
        ready=ready,
        reason=reason,
        active_providers=providers,
    )


@router.get("/health/ready")
def readiness_check(engine: GripEngine = Depends(get_engine)):
    """Kubernetes/Docker readiness probe."""
    ready, reason = engine.ready()
    return {"ready": ready, "reason": reason}
