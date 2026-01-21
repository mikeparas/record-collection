import uuid
from typing import cast
from unittest.mock import AsyncMock, Mock

import pytest
from aio_pika import DeliveryMode, Message
from aio_pika.exceptions import AMQPError

from src.modules.artists.models import ArtistModel
from src.modules.artists.publisher import ROUTING_KEY, ArtistPublisher
from src.modules.artists.schemas import ArtistMessage


@pytest.mark.asyncio
async def test_publish_message():
    mock_channel = AsyncMock()
    mock_exchange = AsyncMock()
    mock_exchange.publish = AsyncMock()

    mock_channel.get_exchange = AsyncMock()
    mock_channel.get_exchange.return_value = mock_exchange

    exchange = "test_exchange"

    publisher = ArtistPublisher(channel=mock_channel, exchange_name=exchange)
    artist = ArtistModel(
        name="Test Artist", sort_name="testartist", discogs_id="1234abcd"
    )
    artist.id = uuid.uuid4()
    artist_message = ArtistMessage.model_validate(artist)
    result = await publisher.publish_message(artist_message)

    assert result is True

    cast(AsyncMock, mock_channel.get_exchange).assert_awaited_once_with(
        exchange, ensure=False
    )

    mock_publish = cast(AsyncMock, mock_exchange.publish)
    mock_publish.assert_awaited_once()
    args, kwargs = mock_publish.call_args
    expected_message = cast(Message, args[0])
    assert (
        expected_message.body == artist_message.model_dump_json(by_alias=True).encode()
    )
    assert expected_message.content_type == "application/json"
    assert expected_message.delivery_mode == DeliveryMode.PERSISTENT
    assert kwargs["routing_key"] == ROUTING_KEY


@pytest.mark.asyncio
async def test_publish_message_queue_error():
    mock_channel = AsyncMock()

    mock_channel.get_exchange = AsyncMock()
    mock_channel.get_exchange.side_effect = AMQPError()

    exchange = "test_exchange"

    publisher = ArtistPublisher(channel=mock_channel, exchange_name=exchange)
    artist = ArtistModel(
        name="Test Artist", sort_name="testartist", discogs_id="1234abcd"
    )
    artist.id = uuid.uuid4()
    artist_message = ArtistMessage.model_validate(artist)
    result = await publisher.publish_message(artist_message)

    assert result is False
    cast(AsyncMock, mock_channel.get_exchange).assert_awaited_once_with(
        exchange, ensure=False
    )


@pytest.mark.asyncio
async def test_publish_message_other_error():
    mock_channel = AsyncMock()

    mock_channel.get_exchange = AsyncMock()
    mock_channel.get_exchange.return_value = AsyncMock()

    exchange = "test_exchange"

    publisher = ArtistPublisher(channel=mock_channel, exchange_name=exchange)
    mock_artist_message = Mock()
    mock_artist_message.model_dump_json = Mock(side_effect=Exception("testing"))

    result = await publisher.publish_message(mock_artist_message)

    assert result is False
