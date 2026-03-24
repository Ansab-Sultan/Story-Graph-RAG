"""Health-check endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.dependencies import get_container
from app.schemas.common import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(container=Depends(get_container)) -> HealthResponse:
    services = await container.database_manager.ping()
    status = "ok" if all(value == "ok" for value in services.values()) else "degraded"
    return HealthResponse(status=status, services=services)

