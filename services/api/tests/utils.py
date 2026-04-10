import base64
import itertools
import json
import os
import re
import time
import uuid
from typing import Any, cast
from urllib.parse import ParseResult, parse_qs, urlparse

from aio_pika import DeliveryMode
from aio_pika.abc import AbstractMessage

from src.modules.artists.models import ArtistModel
from src.modules.artists.publisher import MESSAGE_TYPE, ROUTING_KEY
from src.modules.labels.models import LabelModel
from src.modules.records.models import RecordData, RecordModel


def generate_artists(limit: int = 10, skip_id: bool = False) -> list[ArtistModel]:
    artists: list[ArtistModel] = []
    for i in range(1, limit + 1):
        artist = ArtistModel(name=f"Artist {i:02}", sort_name=f"artist{i:02}")
        if not skip_id:
            artist.id = uuid.uuid4()
        artists.append(artist)
    return artists


def generate_labels(limit: int = 10, skip_id: bool = False) -> list[LabelModel]:
    labels: list[LabelModel] = []
    for i in range(1, limit + 1):
        label = LabelModel(name=f"Label {i:02}", sort_name=f"label{i:02}")
        if not skip_id:
            label.id = uuid.uuid4()
        labels.append(label)
    return labels


def encode_cursor(sort_name: str, attr_name: str = "sort_name") -> str:
    # build payload
    payload = {attr_name: sort_name}

    json_bytes = json.dumps(payload).encode("utf8")

    # base64 encode
    # remove trailing "="
    encoded_bytes = base64.urlsafe_b64encode(json_bytes).rstrip(b"=")

    return encoded_bytes.decode("utf8")


def assert_pagination(
    body: dict[str, Any],
    expected_limit: int,
    expected_cursor: str | None,
    link_path: str,
    additional_params: dict[str, str] | None = None,
):
    pagination = body.get("pagination")
    assert pagination is not None
    assert pagination["limit"] == expected_limit

    next_cursor = pagination.get("nextCursor")
    assert next_cursor == expected_cursor

    next_link = pagination.get("nextLink")
    if expected_cursor is not None:
        assert next_link is not None
        url_parts = cast(ParseResult, urlparse(next_link))
        assert url_parts.path == link_path
        query_params = parse_qs(url_parts.query)
        assert int(query_params["limit"][0]) == expected_limit
        assert query_params["cursor"][0] == next_cursor
        if additional_params is not None and len(additional_params) > 0:
            for k, v in additional_params.items():
                assert query_params[k][0] == v

    else:
        assert next_link is None


def generate_record_sort_keys(
    artist_sort_name: str, label_sort_name: str, year: int, title: str
):
    return {
        "sk_artist_year": f"{artist_sort_name}{year}{title}",
        "sk_artist_title": f"{artist_sort_name}{title}",
        "sk_label_artist_year": f"{label_sort_name}{artist_sort_name}{year}{title}",
        "sk_label_year_artist": f"{label_sort_name}{year}{artist_sort_name}{title}",
    }


def generate_records(limit: int, skip_ids: bool = False):
    # artists
    artists = [
        ArtistModel(name="Punitive Damage", sort_name="punitivedamage"),
        ArtistModel(name="Modern Life Is War", sort_name="modernlifeiswar"),
        ArtistModel(name="No Idols", sort_name="noidols"),
    ]
    labels = [
        LabelModel(name="Iron Lung Records", sort_name="ironlungrecords"),
        LabelModel(name="Deathwish, Inc.", sort_name="deathwishinc"),
    ]

    # for entity in artists + labels:
    # db.add(entity)

    # setup cycles for record data
    artist_cycle = itertools.cycle(artists)
    label_cycle = itertools.cycle(labels)
    formats = itertools.cycle(["LP", '7"', '12" EP', "2xLP"])
    year_cycle = itertools.cycle([2000, 2001, 2002, 2018, 2019, 2024, 2025])

    records: list[RecordModel] = []

    for i in range(1, limit + 1):
        artist = next(artist_cycle)
        label = next(label_cycle)
        format_ = next(formats)
        year = next(year_cycle)

        title = f"Test Record {i:02}"

        record_item = RecordModel(
            title=title,
            format_=format_,
            year_release=year,
            year_pressing=year,
            data=RecordData(color="Black vinyl", notes=f"Test {i}"),
            artists=[artist],
            labels=[label],
            **generate_record_sort_keys(artist.sort_name, label.sort_name, year, title),
        )

        # db.add(record_item)
        records.append(record_item)

    if not skip_ids:
        for entity in artists + labels + records:
            entity.id = uuid.uuid4()

    return records, artists, labels


def assert_record_list_item(expected_item: RecordModel, received_item: dict[str, Any]):
    expected_json = {
        "id": str(expected_item.id),
        "title": expected_item.title,
        "format": expected_item.format_,
        "yearRelease": expected_item.year_release,
        "yearPressing": expected_item.year_pressing,
        "data": {"color": expected_item.data.color, "notes": expected_item.data.notes},
        "sortArtistYear": expected_item.sk_artist_year,
        "sortArtistTitle": expected_item.sk_artist_title,
        "sortLabelArtistYear": expected_item.sk_label_artist_year,
        "sortLabelYearArtist": expected_item.sk_label_year_artist,
        "artists": [
            {
                "id": str(expected_item.artists[0].id),
                "name": expected_item.artists[0].name,
            }
        ],
        "labels": [
            {
                "id": str(expected_item.labels[0].id),
                "name": expected_item.labels[0].name,
            }
        ],
    }
    assert received_item == expected_json


def rmq_test_exchange_name():
    base_name = os.getenv("MQ_EXCHANGE", "record_collection")
    return f"test-{time.time()}-{base_name}"


def rmq_test_queue_name():
    base_name = os.getenv("MQ_QUEUE_EXTERNAL_DATA", "external_data_v1")
    return f"test-{time.time()}-{base_name}"


def assert_artist_message_properties(
    message: AbstractMessage,
    artist_id: uuid.UUID,
    actual_routing_key: str,
    expected_routing_key: str = ROUTING_KEY,
    expected_type: str = MESSAGE_TYPE,
    expected_correlation_id: str | None = None,
) -> None:
    """Assert that the AMQP message has expected properties and body.

    Args:
        message: The AMQP message to validate
        artist_id: The expected artist ID in the message body
        routing_key: The expected routing key (defaults to ROUTING_KEY)
        expected_correlation_id: Optional correlation ID to assert matches the message
    """
    # Verify message body contains only artist_id
    body = json.loads(message.body)
    assert body["artistId"] == str(artist_id)

    # Verify AMQP message properties
    assert message.type == expected_type
    assert message.message_id is not None
    assert message.correlation_id is not None
    assert message.timestamp is not None
    assert message.content_type == "application/json"
    assert message.delivery_mode == DeliveryMode.PERSISTENT

    # Verify UUID format for message_id and correlation_id
    assert re.match(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        message.message_id,
    ), f"message_id {message.message_id} is not a valid UUID"
    assert re.match(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        message.correlation_id,
    ), f"correlation_id {message.correlation_id} is not a valid UUID"

    # Verify routing key
    assert actual_routing_key == expected_routing_key

    # If expected correlation_id provided, verify it matches
    if expected_correlation_id is not None:
        assert message.correlation_id == expected_correlation_id
