import os
from http import HTTPStatus
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.dependencies import get_health_service
from src.modules.health.router import router
from src.modules.health.schemas import HealthCheck
from src.modules.health.service import Status

app = FastAPI()
app.include_router(router)

BASE_PATH = "/health"


@pytest_asyncio.fixture
async def async_client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_get_health_live(async_client: AsyncClient):
    response = await async_client.get(f"{BASE_PATH}/live")
    assert response.status_code == HTTPStatus.OK
    health = response.json()
    assert health["status"] == "healthy"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,db_status,queue_status,main_status",
    [
        (BASE_PATH, Status.HEALTHY, Status.HEALTHY, Status.HEALTHY),
        (BASE_PATH, Status.UNHEALTHY, Status.UNHEALTHY, Status.UNHEALTHY),
        (f"{BASE_PATH}/ready", Status.HEALTHY, Status.HEALTHY, Status.HEALTHY),
        (f"{BASE_PATH}/ready", Status.UNHEALTHY, Status.UNHEALTHY, Status.UNHEALTHY),
    ],
)
async def test_get_health_ready(
    path: str,
    db_status: Status,
    queue_status: Status,
    main_status: Status,
    async_client: AsyncClient,
):
    mock_health_service = AsyncMock()
    mock_health_service.check_database = AsyncMock()
    mock_health_service.check_database.return_value = HealthCheck(
        status=db_status, component="database"
    )

    mock_health_service.check_queue = AsyncMock()
    mock_health_service.check_queue.return_value = HealthCheck(
        status=queue_status, component="queue"
    )

    def override_health_service():
        return mock_health_service

    app.dependency_overrides[get_health_service] = override_health_service

    response = await async_client.get(path)
    assert response.status_code == HTTPStatus.OK
    health = response.json()
    assert health["status"] == main_status

    checks = health.get("checks")
    assert checks["database"] == {"status": db_status, "component": "database"}
    assert checks["queue"] == {"status": queue_status, "component": "queue"}

    mock_health_service.check_database.assert_awaited_once()
    mock_health_service.check_queue.assert_awaited_once()
