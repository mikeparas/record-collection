from enum import StrEnum

from aio_pika.abc import AbstractChannel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.health.schemas import HealthCheck, HealthChecks, HealthStatus


class Status(StrEnum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


def database_check(status: Status):
    return HealthCheck(status=status, component="database")


def queue_check(status: Status):
    return HealthCheck(status=status, component="queue")


class HealthService:
    """Service for checking API health and readiness."""

    db: AsyncSession
    channel: AbstractChannel

    def __init__(self, db: AsyncSession, channel: AbstractChannel):
        self.db = db
        self.channel = channel

    async def check_database(self) -> HealthCheck:
        try:
            await self.db.execute(text("SELECT 1"))
            return HealthCheck(status=Status.HEALTHY, component="database")
        except Exception:
            return HealthCheck(status=Status.UNHEALTHY, component="database")

    async def check_queue(self) -> HealthCheck:
        status = Status.HEALTHY if self.channel.is_initialized else Status.UNHEALTHY
        return HealthCheck(status=status, component="queue")

    async def check_readiness(self) -> HealthStatus:
        """Check if the API and its dependencies are ready."""
        return HealthStatus(
            status=Status.HEALTHY,
            checks=HealthChecks(
                database=database_check(Status.HEALTHY),
                queue=queue_check(Status.HEALTHY),
            ),
        )
