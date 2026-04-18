import re
import uuid
from http import HTTPStatus
from typing import Any
from unittest.mock import MagicMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from src.core.exceptions import (
    NotFoundException,
    not_found_exception_handler,
    request_validation_error_handler,
)
from src.dependencies import get_record_service
from src.modules.artists.models import ArtistModel
from src.modules.labels.models import LabelModel
from src.modules.records.models import RecordData, RecordModel
from src.modules.records.router import router
from src.modules.records.service import (
    DEFAULT_LIST_LIMIT,
    RecordService,
    RecordSortOption,
)
from tests.utils import assert_pagination, encode_cursor, generate_records

app = FastAPI()
app.add_exception_handler(RequestValidationError, request_validation_error_handler)
app.add_exception_handler(NotFoundException, not_found_exception_handler)
app.include_router(router)

client = TestClient(app)

BASE_PATH = "/records"

mock_uuid = uuid.uuid4()
mock_uuid_str = str(mock_uuid)


def assert_service_create_called(mock_fn: Mock, record_data: dict[str, Any]):
    mock_fn.assert_called_once_with(
        title=record_data["title"],
        format_=record_data["format"],
        year_release=record_data["yearRelease"],
        year_pressing=record_data["yearPressing"],
        data=RecordData(
            color=record_data["data"]["color"], notes=record_data["data"]["notes"]
        ),
        artist_ids=[uuid.UUID(record_data["artists"][0])],
        label_ids=[uuid.UUID(record_data["labels"][0])],
        sk_artist_year=record_data["sortArtistYear"],
        sk_artist_title=record_data["sortArtistTitle"],
        sk_label_artist_year=record_data["sortLabelArtistYear"],
        sk_label_year_artist=record_data["sortLabelYearArtist"],
    )


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


@pytest.fixture
def mock_record_service():
    return MagicMock(spec=RecordService)


def test_get_record_success(mock_record_service: MagicMock):
    mock_artist = ArtistModel(name="Test Artist", sort_name="testartist")
    mock_artist.id = uuid.uuid4()

    mock_label = LabelModel(name="Test Label", sort_name="testlabel")
    mock_label.id = uuid.uuid4()

    mock_record = RecordModel(
        title="Test Record",
        format_='7"',
        year_release=2024,
        year_pressing=2024,
        data=RecordData(color="Clear vinyl", notes="Gatefold cover"),
        artists=[mock_artist],
        labels=[mock_label],
        sk_artist_year="testartist2024testrecord",
        sk_artist_title="testartisttestrecord",
        sk_label_artist_year="testlabeltestartist2024testrecord",
        sk_label_year_artist="testlabel2024testartisttestrecord",
    )
    mock_record.id = uuid.uuid4()

    mock_record_service.get_by.return_value = mock_record

    def override_record_service():
        return mock_record_service

    app.dependency_overrides[get_record_service] = override_record_service

    response = client.get(f"{BASE_PATH}/{mock_record.id}")
    assert response.status_code == 200
    record_item = response.json()
    assert record_item["id"] == str(mock_record.id)
    assert record_item["title"] == mock_record.title
    assert record_item["format"] == mock_record.format_
    assert record_item["yearRelease"] == mock_record.year_release
    assert record_item["yearPressing"] == mock_record.year_pressing
    assert record_item["data"] == {
        "color": mock_record.data.color,
        "notes": mock_record.data.notes,
    }
    assert len(record_item["artists"]) == 1
    assert record_item["artists"][0] == {
        "id": str(mock_artist.id),
        "name": mock_artist.name,
    }
    assert len(record_item["labels"]) == 1
    assert record_item["labels"][0] == {
        "id": str(mock_label.id),
        "name": mock_label.name,
    }
    assert record_item["sortArtistYear"] == mock_record.sk_artist_year
    assert record_item["sortArtistTitle"] == mock_record.sk_artist_title
    assert record_item["sortLabelArtistYear"] == mock_record.sk_label_artist_year
    assert record_item["sortLabelYearArtist"] == mock_record.sk_label_year_artist

    mock_record_service.get_by.assert_called_once_with(mock_record.id)


def test_get_record_invalid_id(mock_record_service: MagicMock):
    mock_record_service.get_by.return_value = None

    def override_record_service():
        return mock_record_service

    app.dependency_overrides[get_record_service] = override_record_service

    response = client.get(f"{BASE_PATH}/not-a-uuid")
    assert response.status_code == HTTPStatus.BAD_REQUEST
    body = response.json()
    error = body.get("error")
    assert error is not None
    assert error["type"] == "validation_error"
    assert error["message"] == "Record identifier validation failed."
    assert error["code"] == "RECORD_IDENTIFIER_ERROR"
    assert len(error["details"]) == 1
    assert error["details"][0] == {
        "field": "identifier",
        "code": "non_uuid",
        "message": "Must be a valid UUID.",
    }

    mock_record_service.get_by.assert_not_called()


def test_get_record_not_found(mock_record_service: MagicMock):
    mock_record_service.get_by.return_value = None

    def override_record_service():
        return mock_record_service

    app.dependency_overrides[get_record_service] = override_record_service

    identifier = uuid.uuid4()
    response = client.get(f"{BASE_PATH}/{identifier}")
    assert response.status_code == HTTPStatus.NOT_FOUND
    body = response.json()
    error = body.get("error")
    assert error is not None
    assert error["type"] == "not_found"
    assert error["message"] == f"No record found for {identifier}."
    assert error["code"] == "RECORD_NOT_FOUND"

    mock_record_service.get_by.assert_called_once_with(identifier)


def test_post_record(mock_record_service: MagicMock):
    mock_artist = ArtistModel(name="Test Artist", sort_name="testartist")
    mock_artist.id = uuid.uuid4()

    mock_label = LabelModel(name="Test Label", sort_name="testlabel")
    mock_label.id = uuid.uuid4()

    record_data: dict[str, Any] = {
        "title": "Test Record",
        "format": "LP",
        "yearRelease": 2025,
        "yearPressing": 2025,
        "data": {"color": "Light blue vinyl", "notes": "Repress"},
        "artists": [str(mock_artist.id)],
        "labels": [str(mock_label.id)],
        "sortArtistYear": "testartist2025testrecord",
        "sortArtistTitle": "testartisttestrecord",
        "sortLabelArtistYear": "testlabeltestartist2025testrecord",
        "sortLabelYearArtist": "testlabel2025testartisttestrecord",
    }

    mock_record = RecordModel(
        title=record_data["title"],
        format_=record_data["format"],
        year_release=record_data["yearRelease"],
        year_pressing=record_data["yearPressing"],
        data=RecordData(
            color=record_data["data"]["color"], notes=record_data["data"]["notes"]
        ),
        artists=[mock_artist],
        labels=[mock_label],
        sk_artist_year=record_data["sortLabelArtistYear"],
        sk_artist_title=record_data["sortArtistTitle"],
        sk_label_artist_year=record_data["sortLabelArtistYear"],
        sk_label_year_artist=record_data["sortLabelYearArtist"],
    )
    mock_record.id = uuid.uuid4()

    mock_record_service.create.return_value = mock_record

    def override_record_service():
        return mock_record_service

    app.dependency_overrides[get_record_service] = override_record_service

    response = client.post(BASE_PATH, json=record_data)
    assert response.status_code == HTTPStatus.CREATED
    record_item = response.json()
    assert record_item["id"] == str(mock_record.id)
    assert record_item["title"] == record_data["title"]
    assert record_item["format"] == record_data["format"]
    assert record_item["yearRelease"] == record_data["yearRelease"]
    assert record_item["yearPressing"] == record_data["yearPressing"]
    assert record_item["data"] == record_data["data"]
    assert record_item["artists"] == [
        {"id": str(mock_artist.id), "name": mock_artist.name}
    ]
    assert record_item["labels"] == [
        {"id": str(mock_label.id), "name": mock_label.name}
    ]

    headers = response.headers
    assert (
        re.search(f"/records/{str(mock_record.id)}$", headers["Location"]) is not None
    )

    assert_service_create_called(mock_record_service.create, record_data)


@pytest.mark.parametrize(
    "payload,error_details",
    [
        (
            {
                "title": 123,
                "format": "LP",
                "yearRelease": 2025,
                "yearPressing": 2025,
                "data": {
                    "color": "Red vinyl with black splatter",
                    "notes": "Numbered cover",
                },
                "artists": [mock_uuid_str],
                "labels": [mock_uuid_str],
                "sortArtistYear": "sortArtistYear",
                "sortArtistTitle": "sortArtistTitle",
                "sortLabelArtistYear": "sortLabelArtistYear",
                "sortLabelYearArtist": "sortLabelYearArtist",
            },
            [
                {
                    "field": "title",
                    "code": "non_string",
                    "message": "Must be a string value.",
                }
            ],
        ),
        (
            {
                "title": "Test Title",
                "format": "",
                "yearRelease": 2025,
                "yearPressing": 2025,
                "data": {
                    "color": "Red vinyl with black splatter",
                    "notes": "Numbered cover",
                },
                "artists": [mock_uuid_str],
                "labels": [mock_uuid_str],
                "sortArtistYear": "sortArtistYear",
                "sortArtistTitle": "sortArtistTitle",
                "sortLabelArtistYear": "sortLabelArtistYear",
                "sortLabelYearArtist": "sortLabelYearArtist",
            },
            [
                {
                    "field": "format",
                    "code": "non_empty_string",
                    "message": "Must be a non-empty string value.",
                }
            ],
        ),
        (
            {
                "title": "Test Title",
                "format": "   ",
                "yearRelease": 2025,
                "yearPressing": 2025,
                "data": {
                    "color": "Red vinyl with black splatter",
                    "notes": "Numbered cover",
                },
                "artists": [mock_uuid_str],
                "labels": [mock_uuid_str],
                "sortArtistYear": "sortArtistYear",
                "sortArtistTitle": "sortArtistTitle",
                "sortLabelArtistYear": "sortLabelArtistYear",
                "sortLabelYearArtist": "sortLabelYearArtist",
            },
            [
                {
                    "field": "format",
                    "code": "non_empty_string",
                    "message": "Must be a non-empty string value.",
                }
            ],
        ),
        (
            {
                "title": "Test Title",
                "format": "LP",
                "yearRelease": 2025,
                "yearPressing": 2025,
                "data": {"color": "", "notes": "Numbered cover"},
                "artists": [mock_uuid_str],
                "labels": [mock_uuid_str],
                "sortArtistYear": "sortArtistYear",
                "sortArtistTitle": "sortArtistTitle",
                "sortLabelArtistYear": "sortLabelArtistYear",
                "sortLabelYearArtist": "sortLabelYearArtist",
            },
            [
                {
                    "field": "data.color",
                    "code": "non_empty_string",
                    "message": "Must be a non-empty string value.",
                }
            ],
        ),
        (
            {
                "title": "Test Title",
                "format": "LP",
                "yearRelease": -1,
                "yearPressing": "foobar",
                "data": {"color": "Blue", "notes": "Numbered cover"},
                "artists": [mock_uuid_str],
                "labels": [mock_uuid_str],
                "sortArtistYear": "sortArtistYear",
                "sortArtistTitle": "sortArtistTitle",
                "sortLabelArtistYear": "sortLabelArtistYear",
                "sortLabelYearArtist": "sortLabelYearArtist",
            },
            [
                {
                    "field": "yearRelease",
                    "code": "negative_number",
                    "message": "Must be a positive value.",
                },
                {
                    "field": "yearPressing",
                    "code": "non_integer",
                    "message": "Must be an integer value.",
                },
            ],
        ),
        (
            {
                "title": "Test Title",
                "format": "LP",
                "yearRelease": 2025,
                "yearPressing": 2025,
                "data": {"color": "Blue", "notes": "Numbered cover"},
                "artists": 123,
                "labels": [1234],
                "sortArtistYear": "sortArtistYear",
                "sortArtistTitle": "sortArtistTitle",
                "sortLabelArtistYear": "sortLabelArtistYear",
                "sortLabelYearArtist": "sortLabelYearArtist",
            },
            [
                {
                    "field": "artists",
                    "code": "non_list",
                    "message": "Must be a list value.",
                },
                {
                    "field": "labels.0",
                    "code": "non_uuid",
                    "message": "Must be a valid UUID.",
                },
            ],
        ),
        (
            {
                "title": "Test Title",
                "format": "LP",
                "yearRelease": 2025,
                "yearPressing": 2025,
                "data": {"color": "Blue", "notes": "Numbered cover"},
                "artists": [mock_uuid_str],
                "labels": [mock_uuid_str],
                "sortArtistYear": "",
                "sortArtistTitle": "  ",
                "sortLabelArtistYear": 1234,
                "sortLabelYearArtist": " ",
            },
            [
                {
                    "field": "sortArtistYear",
                    "code": "non_empty_string",
                    "message": "Must be a non-empty string value.",
                },
                {
                    "field": "sortArtistTitle",
                    "code": "non_empty_string",
                    "message": "Must be a non-empty string value.",
                },
                {
                    "field": "sortLabelArtistYear",
                    "code": "non_string",
                    "message": "Must be a string value.",
                },
                {
                    "field": "sortLabelYearArtist",
                    "code": "non_empty_string",
                    "message": "Must be a non-empty string value.",
                },
            ],
        ),
    ],
)
def test_post_records_input_validation(
    payload: dict[str, Any],
    error_details: dict[str, Any],
    mock_record_service: MagicMock,
):
    mock_record_service.create.return_value = None

    def override_record_service():
        return mock_record_service

    app.dependency_overrides[get_record_service] = override_record_service

    response = client.post(BASE_PATH, json=payload)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    body = response.json()
    error = body.get("error")
    assert error is not None
    assert error["type"] == "validation_error"
    assert error["code"] == "RECORD_VALIDATION_ERROR"
    assert error["message"] == "Record data validation failed."
    assert len(error["details"]) == len(error_details)
    for d in error_details:
        assert d in error["details"]

    # input validation should happen before the service call
    mock_record_service.create.assert_not_called()


def test_post_records_missing_relationship(mock_record_service: MagicMock):
    missing_uuid = str(uuid.uuid4())
    mock_record_service.create.side_effect = RequestValidationError(
        [
            {
                "loc": ["body", "artists"],
                "type": "invalid_reference",
                "msg": f"Artists not found: [{missing_uuid}]",
            }
        ]
    )

    def override_record_service():
        return mock_record_service

    app.dependency_overrides[get_record_service] = override_record_service

    record_data: dict[str, Any] = {
        "title": "Hardcore LP",
        "format": "LP",
        "yearRelease": 2025,
        "yearPressing": 2025,
        "data": {"color": "Red vinyl with black splatter", "notes": "Numbered cover"},
        "artists": [missing_uuid],
        "labels": [str(uuid.uuid4())],
        "sortArtistYear": "sortartistyear",
        "sortArtistTitle": "sortartisttitle",
        "sortLabelArtistYear": "sortlabelartistyear",
        "sortLabelYearArtist": "sortlabelyearartist",
    }

    response = client.post(BASE_PATH, json=record_data)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    body = response.json()
    error = body.get("error")
    assert error is not None
    assert error["type"] == "validation_error"
    assert error["code"] == "RECORD_VALIDATION_ERROR"
    assert error["message"] == "Record data validation failed."
    assert {
        "field": "artists",
        "code": "invalid_reference",
        "message": f"Artists not found: [{missing_uuid}]",
    }

    assert_service_create_called(mock_record_service.create, record_data)


def test_get_records_list(mock_record_service: MagicMock):
    mock_records, _, _ = generate_records(28)
    sorted_mock_records = sorted(mock_records, key=lambda r: r.sk_artist_year)[
        :DEFAULT_LIST_LIMIT
    ]
    last_sort_key = sorted_mock_records[-1].sk_artist_year

    mock_record_service.list.return_value = (sorted_mock_records, last_sort_key)

    def override_record_service():
        return mock_record_service

    app.dependency_overrides[get_record_service] = override_record_service

    response = client.get(BASE_PATH)
    assert response.status_code == HTTPStatus.OK
    body = response.json()

    data = body.get("data")
    assert len(data) == DEFAULT_LIST_LIMIT

    # check order
    assert data[0]["sortArtistYear"] == sorted_mock_records[0].sk_artist_year
    assert data[-1]["sortArtistYear"] == sorted_mock_records[-1].sk_artist_year

    # assert one item
    assert_record_list_item(sorted_mock_records[0], data[0])

    last_sort_key = data[-1]["sortArtistYear"]
    assert_pagination(
        body,
        DEFAULT_LIST_LIMIT,
        encode_cursor(last_sort_key, "sort_key"),
        BASE_PATH,
        {"sort": RecordSortOption.ARTIST_YEAR},
    )

    mock_record_service.list.assert_called_once_with(
        limit=DEFAULT_LIST_LIMIT,
        last_cursor=None,
        sort_key_name=RecordSortOption.ARTIST_YEAR,
    )


def test_get_records_list_limit(mock_record_service: MagicMock):
    limit = 15
    mock_records, _, _ = generate_records(28)
    sorted_mock_records = sorted(mock_records, key=lambda r: r.sk_artist_year)[:limit]
    last_sort_key = sorted_mock_records[-1].sk_artist_year

    mock_record_service.list.return_value = (sorted_mock_records, last_sort_key)

    def override_record_service():
        return mock_record_service

    app.dependency_overrides[get_record_service] = override_record_service

    response = client.get(BASE_PATH, params={"limit": limit})
    assert response.status_code == HTTPStatus.OK
    body = response.json()

    data = body.get("data")
    assert len(data) == limit

    # check order
    assert data[0]["sortArtistYear"] == sorted_mock_records[0].sk_artist_year
    assert data[-1]["sortArtistYear"] == sorted_mock_records[-1].sk_artist_year

    # assert one item
    assert_record_list_item(sorted_mock_records[0], data[0])

    last_sort_key = data[-1]["sortArtistYear"]
    assert_pagination(body, limit, encode_cursor(last_sort_key, "sort_key"), BASE_PATH)

    mock_record_service.list.assert_called_once_with(
        limit=limit,
        last_cursor=None,
        sort_key_name=RecordSortOption.ARTIST_YEAR,
    )


def test_get_records_list_cursor(mock_record_service: MagicMock):
    mock_records, _, _ = generate_records(DEFAULT_LIST_LIMIT)
    sorted_mock_records = sorted(mock_records, key=lambda r: r.sk_artist_year)
    last_sort_key = sorted_mock_records[-1].sk_artist_year
    cursor = "lastsortkey"
    token = encode_cursor(cursor, "sort_key")

    mock_record_service.list.return_value = (sorted_mock_records, last_sort_key)

    def override_record_service():
        return mock_record_service

    app.dependency_overrides[get_record_service] = override_record_service

    response = client.get(BASE_PATH, params={"cursor": token})
    assert response.status_code == HTTPStatus.OK
    body = response.json()

    data = body.get("data")
    assert len(data) == DEFAULT_LIST_LIMIT

    # check order
    assert data[0]["sortArtistYear"] == sorted_mock_records[0].sk_artist_year
    assert data[-1]["sortArtistYear"] == sorted_mock_records[-1].sk_artist_year

    # assert one item
    assert_record_list_item(sorted_mock_records[0], data[0])

    last_sort_key = data[-1]["sortArtistYear"]
    assert_pagination(
        body, DEFAULT_LIST_LIMIT, encode_cursor(last_sort_key, "sort_key"), BASE_PATH
    )

    mock_record_service.list.assert_called_once_with(
        limit=DEFAULT_LIST_LIMIT,
        last_cursor=cursor,
        sort_key_name=RecordSortOption.ARTIST_YEAR,
    )


@pytest.mark.parametrize(
    "sort_attr,sort_name,data_sort",
    [
        ("sk_artist_year", "artist_year", "sortArtistYear"),
        ("sk_artist_title", "artist_title", "sortArtistTitle"),
        ("sk_label_artist_year", "label_artist_year", "sortLabelArtistYear"),
        ("sk_label_year_artist", "label_year_artist", "sortLabelYearArtist"),
        # invalid sort name should default to artist_year
        ("sk_artist_year", "invalid", "sortArtistYear"),
    ],
)
def test_get_records_list_sort(
    sort_attr: str, sort_name: str, data_sort: str, mock_record_service: MagicMock
):
    mock_records, _, _ = generate_records(DEFAULT_LIST_LIMIT)
    sorted_mock_records = sorted(mock_records, key=lambda r: getattr(r, sort_attr))
    last_sort_key = getattr(sorted_mock_records[-1], sort_attr)

    mock_record_service.list.return_value = (sorted_mock_records, last_sort_key)

    def override_record_service():
        return mock_record_service

    app.dependency_overrides[get_record_service] = override_record_service

    params: dict[str, Any] = {"sort": sort_name}
    response = client.get(BASE_PATH, params=params)
    assert response.status_code == HTTPStatus.OK
    body = response.json()

    data = body.get("data")
    assert len(data) == DEFAULT_LIST_LIMIT

    # check order
    assert data[0][data_sort] == getattr(sorted_mock_records[0], sort_attr)
    assert data[-1][data_sort] == getattr(sorted_mock_records[-1], sort_attr)

    # assert one item
    assert_record_list_item(sorted_mock_records[0], data[0])

    last_sort_key = data[-1][data_sort]
    assert_pagination(
        body,
        DEFAULT_LIST_LIMIT,
        encode_cursor(last_sort_key, "sort_key"),
        BASE_PATH,
        {"sort": sort_name if sort_name != "invalid" else "artist_year"},
    )

    mock_record_service.list.assert_called_once_with(
        limit=DEFAULT_LIST_LIMIT,
        last_cursor=None,
        sort_key_name=sort_name if sort_name != "invalid" else "artist_year",
    )


def test_list_last_page(mock_record_service: MagicMock):
    mock_records, _, _ = generate_records(12)
    sorted_mock_records = sorted(mock_records, key=lambda r: r.sk_artist_year)

    mock_record_service.list.return_value = (sorted_mock_records, None)

    def override_record_service():
        return mock_record_service

    app.dependency_overrides[get_record_service] = override_record_service

    response = client.get(BASE_PATH)
    assert response.status_code == HTTPStatus.OK
    body = response.json()

    data = body.get("data")
    assert len(data) == len(sorted_mock_records)

    # check order
    assert data[0]["sortArtistYear"] == sorted_mock_records[0].sk_artist_year
    assert data[-1]["sortArtistYear"] == sorted_mock_records[-1].sk_artist_year

    # assert one item
    assert_record_list_item(sorted_mock_records[0], data[0])

    assert_pagination(
        body,
        DEFAULT_LIST_LIMIT,
        None,
        BASE_PATH,
        {"sort": "artist_year"},
    )

    mock_record_service.list.assert_called_once_with(
        limit=DEFAULT_LIST_LIMIT, last_cursor=None, sort_key_name="artist_year"
    )
