from http import HTTPStatus

import pytest
import pytest_asyncio
from aio_pika.abc import AbstractChannel
from httpx import ASGITransport, AsyncClient

from src.main import app

BASE_PATH = "/health"

pytestmark = pytest.mark.e2e


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
@pytest.mark.parametrize("path", [BASE_PATH, f"{BASE_PATH}/ready"])
async def test_get_health_ready(
    path: str,
    async_client: AsyncClient,
    setup_async_database: None,
    rabbitmq_channel: AbstractChannel,
):
    response = await async_client.get(path)
    assert response.status_code == HTTPStatus.OK
    health = response.json()
    assert health["status"] == "healthy"

    checks = health.get("checks")
    assert checks["database"] == {"status": "healthy", "component": "database"}
    assert checks["queue"] == {"status": "healthy", "component": "queue"}
