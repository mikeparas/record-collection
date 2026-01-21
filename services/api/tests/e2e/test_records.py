import re
import uuid
from http import HTTPStatus
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from src.core.database import SessionLocal
from src.main import app
from src.modules.artists.models import ArtistModel
from src.modules.labels.models import LabelModel
from src.modules.records.models import RecordData, RecordModel
from src.modules.records.service import DEFAULT_LIST_LIMIT, RecordSortOption
from tests.utils import (
    assert_pagination,
    assert_record_list_item,
    encode_cursor,
    generate_records,
)

# load_dotenv(".env.test")

pytestmark = pytest.mark.e2e

client = TestClient(app)

BASE_PATH = "/records"


# @pytest.fixture(scope="module", autouse=True)
# def setup_db():
#     init_db(os.getenv("DATABASE_URL", ""))


@pytest.fixture(scope="module")
def seed_records():
    db = SessionLocal()
    records, artists, labels = generate_records(32, True)

    for entity in artists + labels + records:
        db.add(entity)

    db.commit()

    yield records

    for record_item in records:
        db.delete(record_item)
    for artist in artists:
        db.delete(artist)
    for label in labels:
        db.delete(label)
    db.commit()
    db.close()


def test_get_record():
    db = SessionLocal()
    artist = ArtistModel(name="Hardcore Band", sort_name="hardcoreband")
    db.add(artist)
    label = LabelModel(name="Hardcore Label", sort_name="hardcorelabel")
    db.add(label)
    record_item = RecordModel(
        title="Hardcore LP",
        format_="LP",
        year_release=2024,
        year_pressing=2024,
        data=RecordData(color="Black vinyl", notes="Alternate cover"),
        sk_artist_year="hardcoreband2024hardcorelp",
        sk_artist_title="hardcorebandhardcorelp",
        sk_label_artist_year="hardcorelabelhardcoreband2024hardcorelp",
        sk_label_year_artist="hardcorelabel2024hardcorebandhardcorelp",
        artists=[artist],
        labels=[label],
    )
    db.add(record_item)
    db.commit()

    response = client.get(f"{BASE_PATH}/{record_item.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(record_item.id)
    assert data["title"] == record_item.title
    assert data["format"] == record_item.format_
    assert data["yearRelease"] == record_item.year_release
    assert data["yearPressing"] == record_item.year_pressing
    assert data["data"] == {
        "color": record_item.data.color,
        "notes": record_item.data.notes,
    }
    assert data["sortArtistYear"] == record_item.sk_artist_year
    assert data["sortArtistTitle"] == record_item.sk_artist_title
    assert data["sortLabelArtistYear"] == record_item.sk_label_artist_year
    assert data["sortLabelYearArtist"] == record_item.sk_label_year_artist
    assert data["artists"] == [{"id": str(artist.id), "name": artist.name}]
    assert data["labels"] == [{"id": str(label.id), "name": label.name}]

    # clean up seeds
    db.delete(record_item)
    db.delete(artist)
    db.delete(label)
    db.commit()

    db.close()


def test_get_record_invalid_id():
    response = client.get(f"{BASE_PATH}/not-a-uuid-foo")
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


def test_get_record_not_found():
    identifier = uuid.uuid4()

    response = client.get(f"{BASE_PATH}/{identifier}")
    assert response.status_code == HTTPStatus.NOT_FOUND
    body = response.json()
    error = body.get("error")
    assert error is not None
    assert error["type"] == "not_found"
    assert error["message"] == f"No record found for {identifier}."
    assert error["code"] == "RECORD_NOT_FOUND"


def test_post_record_success() -> None:
    # seed an artist and a label
    db = SessionLocal()
    artist = ArtistModel(name="Hardcore Band", sort_name="hardcoreband")
    db.add(artist)
    label = LabelModel(name="Hardcore Label", sort_name="hardcorelabel")
    db.add(label)
    db.commit()

    record_data: dict[str, Any] = {
        "title": "Hardcore LP",
        "format": "LP",
        "yearRelease": 2025,
        "yearPressing": 2025,
        "data": {"color": "Red vinyl with black splatter", "notes": "Numbered cover"},
        "artists": [str(artist.id)],
        "labels": [str(label.id)],
        "sortArtistYear": "hardcoreband2025hardcorelp",
        "sortArtistTitle": "hardcorebandhardcorelp",
        "sortLabelArtistYear": "hardcorelabelhardcoreband2025hardcorelp",
        "sortLabelYearArtist": "hardcorelabel2025hardcorebandhardcorelp",
    }

    response = client.post(BASE_PATH, json=record_data)
    assert response.status_code == HTTPStatus.CREATED
    record_item = response.json()
    assert record_item["id"] is not None
    assert record_item["title"] == record_data["title"]
    assert record_item["format"] == record_data["format"]
    assert record_item["yearRelease"] == record_data["yearRelease"]
    assert record_item["yearPressing"] == record_data["yearPressing"]
    assert record_item["data"] == record_data["data"]
    assert record_item["artists"] == [{"id": str(artist.id), "name": artist.name}]
    assert record_item["labels"] == [{"id": str(label.id), "name": label.name}]
    assert record_item["sortArtistYear"] == record_data["sortArtistYear"]
    assert record_item["sortArtistTitle"] == record_data["sortArtistTitle"]
    assert record_item["sortLabelArtistYear"] == record_data["sortLabelArtistYear"]
    assert record_item["sortLabelYearArtist"] == record_data["sortLabelYearArtist"]

    headers = response.headers
    assert re.search(f"/records/{record_item['id']}$", headers["Location"]) is not None

    # clean up db
    # get the record
    stmt = select(RecordModel).where(RecordModel.id == uuid.UUID(record_item["id"]))
    result = db.scalars(stmt)
    rec = result.one_or_none()
    assert rec is not None  # checks that it's in database

    db.delete(rec)
    db.delete(artist)
    db.delete(label)
    db.commit()
    db.close()


def test_post_records_input_validation() -> None:
    mock_uuid = str(uuid.uuid4())
    record_data: dict[str, Any] = {
        "title": 123,
        "format": "LP",
        "yearRelease": 2025,
        "yearPressing": 2025,
        "data": {"color": "Red vinyl with black splatter", "notes": "Numbered cover"},
        "artists": [mock_uuid],
        "labels": [mock_uuid],
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
        "field": "title",
        "code": "non_string",
        "message": "Must be a string value.",
    } in error["details"]


def test_post_records_missing_relationship() -> None:
    # seed an artist and a label
    db = SessionLocal()
    artist = ArtistModel(name="Hardcore Band", sort_name="hardcoreband")
    db.add(artist)
    label = LabelModel(name="Hardcore Label", sort_name="hardcorelabel")
    db.add(label)
    db.commit()

    missing_artist_id = uuid.uuid4()

    record_data: dict[str, Any] = {
        "title": "Hardcore LP",
        "format": "LP",
        "yearRelease": 2025,
        "yearPressing": 2025,
        "data": {"color": "Red vinyl with black splatter", "notes": "Numbered cover"},
        "artists": [str(artist.id), str(missing_artist_id)],
        "labels": [str(label.id)],
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
        "message": f"Artists not found: [{str(missing_artist_id)}]",
    }

    db.delete(artist)
    db.delete(label)
    db.commit()
    db.close()


def test_get_records_list(seed_records: list[RecordModel]):
    response = client.get(BASE_PATH)
    assert response.status_code == HTTPStatus.OK
    body = response.json()

    data = body.get("data")
    assert len(data) == DEFAULT_LIST_LIMIT

    expected_sorted = sorted(seed_records, key=lambda r: r.sk_artist_year)[
        :DEFAULT_LIST_LIMIT
    ]
    # assert order
    assert data[0]["id"] == str(expected_sorted[0].id)
    assert data[-1]["id"] == str(expected_sorted[-1].id)

    # assert one item
    first_item = expected_sorted[0]
    assert_record_list_item(first_item, data[0])

    last_sort_key = data[-1]["sortArtistYear"]
    assert_pagination(
        body,
        DEFAULT_LIST_LIMIT,
        encode_cursor(last_sort_key, "sort_key"),
        BASE_PATH,
        {"sort": RecordSortOption.ARTIST_YEAR},
    )


def test_get_records_list_limit(seed_records: list[RecordModel]):
    limit = 15  # something smaller than the default
    response = client.get(BASE_PATH, params={"limit": limit})
    assert response.status_code == HTTPStatus.OK
    body = response.json()

    data = body.get("data")
    assert len(data) == limit

    expected_sorted = sorted(seed_records, key=lambda r: r.sk_artist_year)[:limit]
    # assert order
    assert data[0]["id"] == str(expected_sorted[0].id)
    assert data[-1]["id"] == str(expected_sorted[-1].id)

    # assert one item
    first_item = expected_sorted[0]
    assert_record_list_item(first_item, data[0])

    last_sort_key = data[-1]["sortArtistYear"]
    assert_pagination(
        body,
        limit,
        encode_cursor(last_sort_key, "sort_key"),
        BASE_PATH,
        {"sort": RecordSortOption.ARTIST_YEAR},
    )


@pytest.mark.parametrize("limit,start_idx", [(DEFAULT_LIST_LIMIT, 6), (20, 6)])
def test_get_records_list_cursor(
    limit: int, start_idx: int, seed_records: list[RecordModel]
):
    expected_sorted = sorted(seed_records, key=lambda r: r.sk_artist_year)
    last_sort_key = expected_sorted[start_idx - 1].sk_artist_year
    token = encode_cursor(last_sort_key, "sort_key")

    params: dict[str, Any] = (
        {"cursor": token, "limit": limit}
        if limit != DEFAULT_LIST_LIMIT
        else {"cursor": token}
    )
    response = client.get(BASE_PATH, params=params)
    assert response.status_code == HTTPStatus.OK
    body = response.json()

    data = body.get("data")
    assert len(data) == limit

    assert data[0]["id"] == str(expected_sorted[start_idx].id)
    assert data[-1]["id"] == str(expected_sorted[start_idx + limit - 1].id)

    first_item = expected_sorted[start_idx]
    assert_record_list_item(first_item, data[0])

    last_sort_key = data[-1]["sortArtistYear"]
    assert_pagination(
        body,
        limit,
        encode_cursor(last_sort_key, "sort_key"),
        BASE_PATH,
        {"sort": RecordSortOption.ARTIST_YEAR},
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
    sort_attr: str, sort_name: str, data_sort: str, seed_records: list[RecordModel]
):
    # sort_attr = "sk_artist_year"
    expected_sorted = sorted(seed_records, key=lambda r: getattr(r, sort_attr))[
        :DEFAULT_LIST_LIMIT
    ]
    last_sort_key = expected_sorted[-1].sk_artist_year

    params: dict[str, Any] = {"sort": sort_name}
    response = client.get(BASE_PATH, params=params)
    assert response.status_code == HTTPStatus.OK
    body = response.json()

    data = body.get("data")
    assert len(data) == DEFAULT_LIST_LIMIT

    assert data[0]["id"] == str(expected_sorted[0].id)
    assert data[-1]["id"] == str(expected_sorted[-1].id)

    first_item = expected_sorted[0]
    assert_record_list_item(first_item, data[0])

    last_sort_key = data[-1][data_sort]
    assert_pagination(
        body,
        DEFAULT_LIST_LIMIT,
        encode_cursor(last_sort_key, "sort_key"),
        BASE_PATH,
        {"sort": sort_name if sort_name != "invalid" else "artist_year"},
    )


def test_get_records_list_last_page(seed_records: list[RecordModel]):
    sorted_records = sorted(seed_records, key=lambda r: r.sk_artist_year)
    idx = 25
    cursor = encode_cursor(sorted_records[idx].sk_artist_year, "sort_key")

    params = {"cursor": cursor}
    response = client.get(BASE_PATH, params=params)
    assert response.status_code == HTTPStatus.OK
    body = response.json()

    data = body.get("data")
    assert len(data) == len(sorted_records) - idx - 1
    assert data[0]["id"] == str(sorted_records[idx + 1].id)
    assert data[-1]["id"] == str(sorted_records[-1].id)

    first_item = sorted_records[idx + 1]
    assert_record_list_item(first_item, data[0])

    assert_pagination(body, DEFAULT_LIST_LIMIT, None, BASE_PATH)
