import os

import aio_pika
import pytest
import pytest_asyncio
from aio_pika.abc import AbstractRobustConnection
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient

from src.core.database import init_async_db, init_db
from src.core.publisher import RabbitMQConnector
from src.main import app
from tests.utils import rmq_test_exchange_name, rmq_test_queue_name

load_dotenv()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def async_client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest.fixture(scope="module", autouse=True)
def setup_sync_database():
    """Initialize both databases once at module start."""
    init_db(
        database=os.getenv("DB_NAME", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        username=os.getenv("DB_APP_USER", ""),
        password=os.getenv("DB_APP_PASS", ""),
    )

    yield

    # Cleanup after all tests
    from src.core.database import DatabaseConnector

    DatabaseConnector.reset_sync()


@pytest.fixture(scope="function")
def setup_async_database():
    init_async_db(
        database=os.getenv("DB_NAME", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        username=os.getenv("DB_APP_USER", ""),
        password=os.getenv("DB_APP_PASS", ""),
    )

    yield

    from src.core.database import DatabaseConnector

    DatabaseConnector.reset_async()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def rabbitmq_client():
    connection = await RabbitMQConnector.connect(
        host=os.getenv("MQ_HOST", "localhost"),
        port=int(os.getenv("MQ_PORT", "5672")),
        username=os.getenv("MQ_USER", ""),
        password=os.getenv("MQ_PASS", ""),
    )

    yield connection

    await RabbitMQConnector.close()


@pytest.fixture(scope="module")
def rabbitmq_patch():
    with pytest.MonkeyPatch.context() as mp:
        yield mp


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def rabbitmq_queue(
    rabbitmq_client: AbstractRobustConnection, rabbitmq_patch: pytest.MonkeyPatch
):
    async with rabbitmq_client.channel() as channel:
        exchange_name = rmq_test_exchange_name()
        queue_name = rmq_test_queue_name()
        rabbitmq_patch.setenv("MQ_EXCHANGE", exchange_name)
        rabbitmq_patch.setenv("MQ_QUEUE_EXTERNAL_DATA", queue_name)

        exchange = await channel.declare_exchange(
            exchange_name, aio_pika.ExchangeType.TOPIC, durable=False, auto_delete=True
        )

        queue = await channel.declare_queue(
            queue_name, durable=False, auto_delete=True, exclusive=True
        )

        await queue.bind(exchange, routing_key="artist.#")

        await queue.purge()

        yield queue
