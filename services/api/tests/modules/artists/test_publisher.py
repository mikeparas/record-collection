import uuid
from typing import cast
from unittest.mock import AsyncMock

import pytest
from aio_pika import Message
from aio_pika.exceptions import AMQPError

from src.modules.artists.publisher import ArtistPublisher
from src.modules.artists.schemas import ArtistMessage
from tests.utils import assert_artist_message_properties


@pytest.mark.asyncio
async def test_publish_message():
    mock_channel = AsyncMock()
    mock_exchange = AsyncMock()
    mock_exchange.publish = AsyncMock()

    mock_channel.get_exchange = AsyncMock()
    mock_channel.get_exchange.return_value = mock_exchange

    exchange = "test_exchange"

    publisher = ArtistPublisher(channel=mock_channel, exchange_name=exchange)
    artist_id = uuid.uuid4()
    artist_message = ArtistMessage(artist_id=artist_id)
    result = await publisher.publish_message(artist_message)

    assert result is True

    cast(AsyncMock, mock_channel.get_exchange).assert_awaited_once_with(
        exchange, ensure=False
    )

    mock_publish = cast(AsyncMock, mock_exchange.publish)
    mock_publish.assert_awaited_once()
    args, kwargs = mock_publish.call_args
    expected_message = cast(Message, args[0])

    # Assert message properties and body (includes routing_key assertion)
    assert_artist_message_properties(
        expected_message, artist_id, actual_routing_key=kwargs["routing_key"]
    )


@pytest.mark.asyncio
async def test_publish_message_queue_error():
    mock_channel = AsyncMock()

    mock_channel.get_exchange = AsyncMock()
    mock_channel.get_exchange.side_effect = AMQPError()

    exchange = "test_exchange"

    publisher = ArtistPublisher(channel=mock_channel, exchange_name=exchange)
    artist_id = uuid.uuid4()
    artist_message = ArtistMessage(artist_id=artist_id)
    result = await publisher.publish_message(artist_message)

    assert result is False
    cast(AsyncMock, mock_channel.get_exchange).assert_awaited_once_with(
        exchange, ensure=False
    )


@pytest.mark.asyncio
async def test_publish_message_other_error():
    mock_channel = AsyncMock()
    mock_exchange = AsyncMock()
    # Make publish raise an unexpected error (not AMQPError)
    mock_exchange.publish = AsyncMock(side_effect=Exception("Unexpected error"))

    mock_channel.get_exchange = AsyncMock()
    mock_channel.get_exchange.return_value = mock_exchange

    exchange = "test_exchange"

    publisher = ArtistPublisher(channel=mock_channel, exchange_name=exchange)
    artist_id = uuid.uuid4()
    artist_message = ArtistMessage(artist_id=artist_id)

    result = await publisher.publish_message(artist_message)

    assert result is False


@pytest.mark.asyncio
async def test_publish_message_with_explicit_correlation_id():
    mock_channel = AsyncMock()
    mock_exchange = AsyncMock()
    mock_exchange.publish = AsyncMock()

    mock_channel.get_exchange = AsyncMock()
    mock_channel.get_exchange.return_value = mock_exchange

    exchange = "test_exchange"
    explicit_correlation_id = str(uuid.uuid4())

    publisher = ArtistPublisher(channel=mock_channel, exchange_name=exchange)
    artist_id = uuid.uuid4()
    artist_message = ArtistMessage(artist_id=artist_id)
    result = await publisher.publish_message(
        artist_message, correlation_id=explicit_correlation_id
    )

    assert result is True

    mock_publish = cast(AsyncMock, mock_exchange.publish)
    args, kwargs = mock_publish.call_args
    expected_message = cast(Message, args[0])

    # Assert full message properties with expected correlation_id
    assert_artist_message_properties(
        expected_message,
        artist_id,
        actual_routing_key=kwargs["routing_key"],
        expected_correlation_id=explicit_correlation_id,
    )
