from unittest.mock import AsyncMock

import pytest
from sqlalchemy import TextClause, text
from sqlalchemy.dialects import postgresql

from src.modules.health.service import HealthService, Status


def compile_text(text_expr: TextClause) -> str:
    return str(
        text_expr.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )


@pytest.mark.asyncio
async def test_check_database_healthy():
    mock_db = AsyncMock()
    mock_channel = AsyncMock()

    mock_db.execute = AsyncMock()
    # just doesn't throw an exception?
    mock_db.execute.return_value = AsyncMock()

    service = HealthService(mock_db, mock_channel)
    check = await service.check_database()

    assert check.status == Status.HEALTHY
    assert check.component == "database"

    mock_db.execute.assert_awaited_once()
    arg_text = mock_db.execute.call_args[0][0]
    assert compile_text(arg_text) == compile_text(text("SELECT 1"))


@pytest.mark.asyncio
async def test_check_database_unhealthy():
    mock_db = AsyncMock()
    mock_channel = AsyncMock()

    mock_db.execute = AsyncMock()
    mock_db.execute.side_effect = Exception("testing")

    service = HealthService(mock_db, mock_channel)
    check = await service.check_database()

    assert check.status == Status.UNHEALTHY
    assert check.component == "database"

    mock_db.execute.assert_awaited_once()
    arg_text = mock_db.execute.call_args[0][0]
    assert compile_text(arg_text) == compile_text(text("SELECT 1"))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "is_initialized, status", [(True, Status.HEALTHY), (False, Status.UNHEALTHY)]
)
async def test_check_queue_healthy(is_initialized: bool, status: Status):
    mock_db = AsyncMock()
    mock_channel = AsyncMock()

    mock_channel.is_initialized = is_initialized

    service = HealthService(mock_db, mock_channel)
    check = await service.check_queue()

    assert check.status == status
    assert check.component == "queue"
