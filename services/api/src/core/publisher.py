import aio_pika
from aio_pika.abc import AbstractChannel, AbstractRobustConnection


class RabbitMQConnector:
    connection: AbstractRobustConnection | None = None

    @classmethod
    async def connect(
        cls, *, host: str, username: str, password: str, port: int
    ) -> AbstractRobustConnection:
        if cls.connection is not None:
            print("returning cached connection...")
            return cls.connection

        print(f"new rabbitmq connection {host=} {username=} {port=}")
        cls.connection = await aio_pika.connect_robust(
            host=host, login=username, password=password, port=port, virtualhost="/"
        )

        return cls.connection

    @classmethod
    def get_connection(cls):
        if cls.connection is not None:
            return cls.connection
        raise RuntimeError("RabbitMQ connection has not been initialized")

    @classmethod
    async def close(cls):
        if cls.connection is not None:
            print("closing rabbitmq connection...")
            await cls.connection.close()
            cls.connection = None


async def setup_channel(channel: AbstractChannel, exchange_name: str, queue_name: str):
    exchange = await channel.declare_exchange(
        exchange_name, aio_pika.ExchangeType.TOPIC, durable=True
    )

    external_data_queue = await channel.declare_queue(queue_name, durable=True)
    await external_data_queue.bind(exchange, routing_key="artist.#")
