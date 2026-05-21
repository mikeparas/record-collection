import aio_pika
import structlog
from aio_pika.abc import AbstractChannel, AbstractRobustConnection

log = structlog.stdlib.get_logger(module="core.publisher")


class RabbitMQConnector:
    connection: AbstractRobustConnection | None = None

    @classmethod
    async def connect(
        cls, *, host: str, username: str, password: str, port: int
    ) -> AbstractRobustConnection:
        log.info("Getting RabbitMQ connection instance", host=host, port=port)

        if cls.connection is not None:
            log.info("Using existing RabbitMQ connection")
            return cls.connection

        cls.connection = await aio_pika.connect_robust(
            host=host, login=username, password=password, port=port, virtualhost="/"
        )

        log.info("Returning new RabbitMQ connection")

        return cls.connection

    @classmethod
    def get_connection(cls):
        if cls.connection is not None:
            return cls.connection
        raise RuntimeError("RabbitMQ connection has not been initialized")

    @classmethod
    async def close(cls):
        if cls.connection is not None:
            log.info("Closing RabbitMQ connection")
            await cls.connection.close()
            cls.connection = None


async def setup_channel(channel: AbstractChannel, exchange_name: str, queue_name: str):
    exchange = await channel.declare_exchange(
        exchange_name, aio_pika.ExchangeType.TOPIC, durable=True
    )
    log.info("RabbitMQ exchange declared", exchange=exchange_name)

    external_data_queue = await channel.declare_queue(queue_name, durable=True)
    await external_data_queue.bind(exchange, routing_key="artist.#")
    log.info("RabbitMQ queue bound to exchange", queue=queue_name)
