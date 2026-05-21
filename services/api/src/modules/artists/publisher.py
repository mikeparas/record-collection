import uuid
from datetime import UTC, datetime

import structlog
from aio_pika import DeliveryMode, Message
from aio_pika.abc import AbstractChannel
from aio_pika.exceptions import AMQPError

from src.modules.artists.schemas import ArtistMessage

ROUTING_KEY = "artist.created"
MESSAGE_TYPE = "artist.created"

log = structlog.stdlib.get_logger(module="artists.publisher")


def create_artist_message(
    artist: ArtistMessage, correlation_id: str | None = None
) -> Message:
    """Create an AMQP message with metadata properties for an artist event.

    Args:
        artist: The artist message containing artist_id
        correlation_id: Optional correlation ID from request context. If not provided,
                       a new UUID will be generated.

    Returns:
        An AMQP Message with type, message_id, correlation_id, and timestamp properties.
    """
    message_id = str(uuid.uuid4())
    actual_correlation_id = correlation_id or str(uuid.uuid4())
    timestamp = datetime.now(UTC)

    return Message(
        body=artist.model_dump_json(by_alias=True).encode(),
        content_type="application/json",
        delivery_mode=DeliveryMode.PERSISTENT,
        type=MESSAGE_TYPE,
        message_id=message_id,
        correlation_id=actual_correlation_id,
        timestamp=timestamp,
    )


class ArtistPublisher:
    channel: AbstractChannel
    exchange_name: str

    def __init__(self, *, channel: AbstractChannel, exchange_name: str) -> None:
        self.channel = channel
        self.exchange_name = exchange_name

    async def publish_message(
        self, artist: ArtistMessage, correlation_id: str | None = None
    ):
        try:
            exchange = await self.channel.get_exchange(self.exchange_name, ensure=False)
            amqp_message = create_artist_message(artist, correlation_id)
            await exchange.publish(amqp_message, routing_key=ROUTING_KEY)
            log.info("Published artist message", message_id=amqp_message.message_id)
            return True
        except AMQPError as exc:
            log.error("Failed to publish artist message", exc_info=exc)
            return False
        except Exception as exc:
            log.error("Unexpected error occurred", exc_info=exc)
            return False
