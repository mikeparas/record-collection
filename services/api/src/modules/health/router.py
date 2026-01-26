from typing import Annotated

from fastapi import APIRouter, Depends

from src.dependencies import get_health_service
from src.modules.health.schemas import HealthChecks, HealthStatus
from src.modules.health.service import HealthService, Status

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def get_health_live():
    """Check if the API is accessible."""
    return {"status": "healthy"}


@router.get("")
@router.get("/ready")
async def get_health_ready(
    service: Annotated[HealthService, Depends(get_health_service)],
):
    """Check if the API and its dependencies are ready."""
    checks = HealthChecks(
        database=await service.check_database(), queue=await service.check_queue()
    )

    status = (
        Status.HEALTHY
        if all(
            [
                check["status"] == Status.HEALTHY
                for check in checks.model_dump().values()
            ]
        )
        else Status.UNHEALTHY
    )
    return HealthStatus(status=status, checks=checks)
