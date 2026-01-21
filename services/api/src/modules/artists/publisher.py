from aio_pika import DeliveryMode, Message
from aio_pika.abc import AbstractChannel
from aio_pika.exceptions import AMQPError

from src.modules.artists.schemas import ArtistMessage

ROUTING_KEY = "artist.created"


class ArtistPublisher:
    channel: AbstractChannel
    exchange_name: str

    def __init__(self, *, channel: AbstractChannel, exchange_name: str) -> None:
        self.channel = channel
        self.exchange_name = exchange_name

    async def publish_message(self, artist: ArtistMessage):
        try:
            exchange = await self.channel.get_exchange(self.exchange_name, ensure=False)

            await exchange.publish(
                Message(
                    body=artist.model_dump_json(by_alias=True).encode(),
                    content_type="application/json",
                    delivery_mode=DeliveryMode.PERSISTENT,
                ),
                routing_key=ROUTING_KEY,
            )
            return True
        except AMQPError as exc:
            print(f"AMPQError: {exc}")
            return False
        except Exception as exc:
            print(f"Unexpected error {exc}")
            return False
