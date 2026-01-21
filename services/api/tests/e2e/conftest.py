import os

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from pytest import MonkeyPatch

from src.core.database import init_async_db, init_db
from src.core.publisher import RabbitMQConnector, setup_channel

load_dotenv()


@pytest.fixture(scope="module", autouse=True)
def setup_sync_database():
    """Initialize both databases once at module start."""
    init_db(
        database=os.getenv("DB_TEST_DATABASE", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        username=os.getenv("DB_TEST_USER", ""),
        password=os.getenv("DB_TEST_PASS", ""),
    )

    yield

    # Cleanup after all tests
    from src.core.database import DatabaseConnector

    DatabaseConnector.reset_sync()


@pytest.fixture(scope="function")
def setup_async_database():
    init_async_db(
        database=os.getenv("DB_TEST_DATABASE", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        username=os.getenv("DB_TEST_USER", ""),
        password=os.getenv("DB_TEST_PASS", ""),
    )

    yield

    from src.core.database import DatabaseConnector

    DatabaseConnector.reset_async()


@pytest_asyncio.fixture(scope="function")
async def rabbitmq_channel(monkeypatch: MonkeyPatch):
    monkeypatch.setenv("MQ_EXCHANGE", os.getenv("MQ_TEST_EXCHANGE", ""))
    monkeypatch.setenv(
        "MQ_QUEUE_EXTERNAL_DATA", os.getenv("MQ_TEST_QUEUE_EXTERNAL_DATA", "")
    )

    connection = await RabbitMQConnector.connect(
        host=os.getenv("MQ_HOST", "localhost"),
        port=int(os.getenv("MQ_PORT", "5672")),
        username=os.getenv("MQ_USER", ""),
        password=os.getenv("MQ_PASS", ""),
    )

    async with connection.channel() as channel:
        queue_name = os.getenv("MQ_QUEUE_EXTERNAL_DATA", "")
        await setup_channel(channel, os.getenv("MQ_EXCHANGE", ""), queue_name)
        queue = await channel.get_queue(queue_name, ensure=False)
        await queue.purge()

    yield channel

    await RabbitMQConnector.close()
