import json
import re
from http import HTTPStatus
from typing import Any

import pytest
from aio_pika.abc import AbstractChannel, AbstractQueue
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import select

from src.core.database import AsyncSessionLocal, SessionLocal
from src.main import app
from src.modules.artists.models import ArtistModel
from src.modules.artists.service import DEFAULT_LIST_LIMIT
from src.shared.types import Integrations
from tests.utils import (
    assert_pagination,
    encode_cursor,
    generate_artists,
)

# load_dotenv()

pytestmark = pytest.mark.e2e

client = TestClient(app)

BASE_PATH = "/artists"
BASE_PATH_ASYNC = "/artists_v2"


@pytest.fixture(scope="module")
def seed_artists():
    # change number to accomodate all tests using the fixture
    mock_artists = generate_artists(58, True)

    db = SessionLocal()
    for mock_artist in mock_artists:
        db.add(mock_artist)
    db.commit()

    yield mock_artists

    for mock_artist in mock_artists:
        db.delete(mock_artist)
    db.commit()


def test_get_artist_by_id():
    db = SessionLocal()

    artist = ArtistModel(name="Test Artist", sort_name="testartist")
    db.add(artist)
    db.commit()

    response = client.get(f"{BASE_PATH}/{artist.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(artist.id)
    assert data["name"] == artist.name
    assert data["sortName"] == artist.sort_name

    # clean up seed
    db.delete(artist)
    db.commit()

    db.close()


def test_get_artist_by_name():
    db = SessionLocal()
    artist = ArtistModel(name="Test Artist", sort_name="testartist")
    db.add(artist)
    db.commit()

    response = client.get(f"{BASE_PATH}/{artist.name}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(artist.id)
    assert data["name"] == artist.name
    assert data["sortName"] == artist.sort_name

    # clean up seed
    db.delete(artist)
    db.commit()

    db.close()


def test_get_artist_not_found():
    # nothing to seed
    name = "Not Found Artist"
    response = client.get(f"{BASE_PATH}/{name}")
    assert response.status_code == 404
    body = response.json()
    error = body.get("error")
    assert error is not None
    assert error["type"] == "not_found"
    assert error["message"] == f"No artist found for {name}."
    assert error["code"] == "ARTIST_NOT_FOUND"


def test_post_artist_success():
    artist_data = {"name": "New Artist", "sortName": "newartist"}

    response = client.post(BASE_PATH, json=artist_data)
    assert response.status_code == HTTPStatus.CREATED
    artist = response.json()
    assert artist["name"] == artist_data["name"]
    assert artist["sortName"] == artist_data["sortName"]
    assert artist["id"] is not None

    headers = response.headers
    assert re.search("/artists/New Artist$", headers["Location"]) is not None

    # check database
    db = SessionLocal()
    stmt = select(ArtistModel).where(ArtistModel.name == artist_data["name"])
    result = db.scalars(stmt)
    db_artist = result.one_or_none()
    assert db_artist is not None
    assert artist["id"] == str(db_artist.id)

    db.delete(db_artist)
    db.commit()
    db.close()


@pytest.mark.parametrize(
    "payload,error_details",
    [
        # check string values
        (
            {"name": 123, "sortName": "string"},
            [
                {
                    "field": "name",
                    "code": "non_string",
                    "message": "Must be a string value.",
                }
            ],
        ),
        (
            {"name": "string", "sortName": []},
            [
                {
                    "field": "sortName",
                    "code": "non_string",
                    "message": "Must be a string value.",
                }
            ],
        ),
        (
            {"name": 123, "sortName": []},
            [
                {
                    "field": "name",
                    "code": "non_string",
                    "message": "Must be a string value.",
                },
                {
                    "field": "name",
                    "code": "non_string",
                    "message": "Must be a string value.",
                },
            ],
        ),
        # check non-empty strings
        (
            {"name": "   ", "sortName": "string"},
            [
                {
                    "field": "name",
                    "code": "non_empty",
                    "message": "Must be a non-empty string value.",
                }
            ],
        ),
        (
            {"name": "string", "sortName": "   "},
            [
                {
                    "field": "sortName",
                    "code": "non_empty",
                    "message": "Must be a non-empty string value.",
                }
            ],
        ),
        (
            {"name": "", "sortName": ""},
            [
                {
                    "field": "name",
                    "code": "non_empty",
                    "message": "Must be a non-empty string value.",
                },
                {
                    "field": "sortName",
                    "code": "non_empty",
                    "message": "Must be a non-empty string value.",
                },
            ],
        ),
        (
            {"name": "string"},
            [
                {
                    "field": "sortName",
                    "code": "missing",
                    "message": "Field is required.",
                },
            ],
        ),
        (
            {"sortName": "string"},
            [
                {
                    "field": "name",
                    "code": "missing",
                    "message": "Field is required.",
                },
            ],
        ),
        (
            {"foobar": "string"},
            [
                {
                    "field": "name",
                    "code": "missing",
                    "message": "Field is required.",
                },
                {
                    "field": "sortName",
                    "code": "missing",
                    "message": "Field is required.",
                },
            ],
        ),
    ],
)
def test_post_artist_validation(
    payload: dict[str, Any], error_details: list[dict[str, str]]
):
    response = client.post(BASE_PATH, json=payload)
    body = response.json()
    print(f"{body=}")
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["type"] == "validation_error"
    assert error["code"] == "ARTIST_VALIDATION_ERROR"
    assert error["message"] == "Artist data validation failed."
    assert len(error["details"]) == len(error_details)
    for d in error_details:
        assert d in error_details


@pytest.mark.parametrize(
    "payload,error_msg",
    [
        (
            {"name": "Test Artist", "sortName": "newtestartist"},
            "An artist with name Test Artist already exists.",
        ),
        (
            {"name": "New Test Artist", "sortName": "testartist"},
            "An artist with sortName testartist already exists.",
        ),
    ],
)
def test_post_artist_duplicate(payload: dict[str, str], error_msg: str):
    # seed artist
    db = SessionLocal()
    artist = ArtistModel(name="Test Artist", sort_name="testartist")
    db.add(artist)
    db.commit()

    response = client.post(BASE_PATH, json=payload)
    assert response.status_code == HTTPStatus.CONFLICT
    error = response.json()["error"]
    assert error["type"] == "conflict"
    assert error["code"] == "ARTIST_ALREADY_EXISTS"
    assert error["message"] == error_msg

    # clean up seed
    db.delete(artist)
    db.commit()

    db.close()


def test_get_artists_list(seed_artists: list[ArtistModel]):
    expected_limit = DEFAULT_LIST_LIMIT
    expected_first_name = "Artist 01"
    expected_first_sort_name = "artist01"

    # no query parameters
    response = client.get(BASE_PATH)
    assert response.status_code == HTTPStatus.OK
    body = response.json()

    data = body.get("data")
    assert data is not None
    assert len(data) == expected_limit
    assert data[0]["name"] == expected_first_name
    assert data[0]["sortName"] == expected_first_sort_name

    last_sort_name = data[-1]["sortName"]
    assert_pagination(body, expected_limit, encode_cursor(last_sort_name), BASE_PATH)


def test_get_artists_list_limit(seed_artists: list[ArtistModel]):
    expected_limit = 25
    expected_first_name = "Artist 01"
    expected_first_sort_name = "artist01"

    response = client.get(BASE_PATH, params={"limit": expected_limit})
    assert response.status_code == HTTPStatus.OK
    body = response.json()

    data = body.get("data")
    assert data is not None
    assert len(data) == expected_limit
    assert data[0]["name"] == expected_first_name
    assert data[0]["sortName"] == expected_first_sort_name

    last_sort_name = data[-1]["sortName"]
    assert_pagination(body, expected_limit, encode_cursor(last_sort_name), BASE_PATH)


@pytest.mark.parametrize("limit,start_idx", [(DEFAULT_LIST_LIMIT, 6), (25, 6)])
def test_get_artists_list_cursor(
    limit: int, start_idx: int, seed_artists: list[ArtistModel]
):
    expected_limit = limit

    cursor_sort_name = seed_artists[start_idx - 1].sort_name
    token = encode_cursor(cursor_sort_name)

    expected_first_name = seed_artists[start_idx].name
    expected_first_sort_name = seed_artists[start_idx].sort_name

    params: dict[str, Any] = (
        {"cursor": token, "limit": limit}
        if limit != DEFAULT_LIST_LIMIT
        else {"cursor": token}
    )
    response = client.get(BASE_PATH, params=params)
    assert response.status_code == HTTPStatus.OK
    body = response.json()

    data = body.get("data")
    assert data is not None
    assert len(data) == expected_limit
    assert data[0]["name"] == expected_first_name
    assert data[0]["sortName"] == expected_first_sort_name

    last_sort_name = data[-1]["sortName"]
    assert_pagination(body, expected_limit, encode_cursor(last_sort_name), BASE_PATH)


def test_get_artists_list_last_page(seed_artists: list[ArtistModel]):
    # pick an artist that will start a "last" page

    idx = 50
    cursor = encode_cursor(seed_artists[idx].sort_name)

    expected_limit = DEFAULT_LIST_LIMIT
    expected_first_name = seed_artists[idx + 1].name
    expected_first_sort_name = seed_artists[idx + 1].sort_name

    response = client.get(BASE_PATH, params={"cursor": cursor})
    assert response.status_code == HTTPStatus.OK
    body = response.json()

    data = body.get("data")
    assert data is not None
    assert len(data) == len(seed_artists) - idx - 1
    assert data[0]["name"] == expected_first_name
    assert data[0]["sortName"] == expected_first_sort_name

    assert_pagination(body, expected_limit, None, BASE_PATH)


#
# START async versions
#


@pytest.mark.asyncio(loop_scope="module")
async def test_async_post_artist_success_no_discogs(
    async_client: AsyncClient,
    setup_async_database: None,
    rabbitmq_queue: AbstractQueue,
):
    artist_data = {"name": "New Artist", "sortName": "newartist"}

    response = await async_client.post(BASE_PATH_ASYNC, json=artist_data)
    assert response.status_code == HTTPStatus.CREATED
    artist = response.json()
    assert artist["name"] == artist_data["name"]
    assert artist["sortName"] == artist_data["sortName"]
    assert artist["id"] is not None
    assert artist["integrations"] is None

    headers = response.headers
    assert re.search(f"{BASE_PATH_ASYNC}/New Artist$", headers["Location"]) is not None

    # check database
    async with AsyncSessionLocal() as db:
        stmt = select(ArtistModel).where(ArtistModel.name == artist_data["name"])
        result = await db.scalars(stmt)
        db_artist = result.one_or_none()
        assert db_artist is not None
        assert artist["id"] == str(db_artist.id)
        assert db_artist.integrations is None

        await db.delete(db_artist)
        await db.commit()


@pytest.mark.asyncio(loop_scope="module")
async def test_async_post_artist_success_with_discogs(
    async_client: AsyncClient,
    rabbitmq_queue: AbstractQueue,
    setup_async_database: None,
):
    artist_data: Any = {
        "name": "New Artist",
        "sortName": "newartist",
        "integrations": {"discogs": 123456},
    }

    response = await async_client.post(BASE_PATH_ASYNC, json=artist_data)
    assert response.status_code == HTTPStatus.CREATED
    artist = response.json()
    assert artist["name"] == artist_data["name"]
    assert artist["sortName"] == artist_data["sortName"]
    assert artist["id"] is not None
    assert artist["integrations"] == artist_data["integrations"]

    headers = response.headers
    assert re.search(f"{BASE_PATH_ASYNC}/New Artist$", headers["Location"]) is not None

    # check database
    async with AsyncSessionLocal() as db:
        stmt = select(ArtistModel).where(ArtistModel.name == artist_data["name"])
        result = await db.scalars(stmt)
        db_artist = result.one_or_none()
        assert db_artist is not None
        assert artist["id"] == str(db_artist.id)
        assert db_artist.integrations is not None and artist_data[
            "integrations"
        ] == Integrations.model_dump(db_artist.integrations)

        await db.delete(db_artist)
        await db.commit()

    # check message queue
    queue = rabbitmq_queue

    message = await queue.get(timeout=2)
    assert message is not None

    async with message.process():
        assert message.routing_key == "artist.created"
        body = json.loads(message.body)
        assert body["artistId"] == artist["id"]


@pytest.mark.asyncio(loop_scope="module")
@pytest.mark.parametrize(
    "payload,error_details",
    [
        # check string values
        (
            {"name": 123, "sortName": "string"},
            [
                {
                    "field": "name",
                    "code": "non_string",
                    "message": "Must be a string value.",
                }
            ],
        ),
        (
            {"name": "string", "sortName": []},
            [
                {
                    "field": "sortName",
                    "code": "non_string",
                    "message": "Must be a string value.",
                }
            ],
        ),
        (
            {"name": 123, "sortName": []},
            [
                {
                    "field": "name",
                    "code": "non_string",
                    "message": "Must be a string value.",
                },
                {
                    "field": "name",
                    "code": "non_string",
                    "message": "Must be a string value.",
                },
            ],
        ),
        # check non-empty strings
        (
            {"name": "   ", "sortName": "string"},
            [
                {
                    "field": "name",
                    "code": "non_empty",
                    "message": "Must be a non-empty string value.",
                }
            ],
        ),
        (
            {"name": "string", "sortName": "   "},
            [
                {
                    "field": "sortName",
                    "code": "non_empty",
                    "message": "Must be a non-empty string value.",
                }
            ],
        ),
        (
            {"name": "", "sortName": ""},
            [
                {
                    "field": "name",
                    "code": "non_empty",
                    "message": "Must be a non-empty string value.",
                },
                {
                    "field": "sortName",
                    "code": "non_empty",
                    "message": "Must be a non-empty string value.",
                },
            ],
        ),
        (
            {"name": "string"},
            [
                {
                    "field": "sortName",
                    "code": "missing",
                    "message": "Field is required.",
                },
            ],
        ),
        (
            {"sortName": "string"},
            [
                {
                    "field": "name",
                    "code": "missing",
                    "message": "Field is required.",
                },
            ],
        ),
        (
            {"foobar": "string"},
            [
                {
                    "field": "name",
                    "code": "missing",
                    "message": "Field is required.",
                },
                {
                    "field": "sortName",
                    "code": "missing",
                    "message": "Field is required.",
                },
            ],
        ),
    ],
)
async def test_async_post_artist_validation(
    payload: dict[str, Any],
    error_details: list[dict[str, str]],
    async_client: AsyncClient,
    setup_async_database: None,
    rabbitmq_queue: AbstractQueue,
):
    response = await async_client.post(BASE_PATH_ASYNC, json=payload)
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["type"] == "validation_error"
    assert error["code"] == "ARTIST_VALIDATION_ERROR"
    assert error["message"] == "Artist data validation failed."
    assert len(error["details"]) == len(error_details)
    for d in error_details:
        assert d in error_details


@pytest.mark.asyncio(loop_scope="module")
@pytest.mark.parametrize(
    "payload,error_msg",
    [
        (
            {"name": "Test Artist", "sortName": "newtestartist"},
            "An artist with name Test Artist already exists.",
        ),
        (
            {"name": "New Test Artist", "sortName": "testartist"},
            "An artist with sortName testartist already exists.",
        ),
    ],
)
async def test_async_post_artist_duplicate(
    payload: dict[str, str],
    error_msg: str,
    async_client: AsyncClient,
    setup_async_database: None,
    rabbitmq_queue: AbstractChannel,
    # seed_duplicate_artist: ArtistModel,
):
    async with AsyncSessionLocal() as db:
        artist = ArtistModel(name="Test Artist", sort_name="testartist")
        db.add(artist)
        await db.commit()
        await db.refresh(artist)

    response = await async_client.post(BASE_PATH_ASYNC, json=payload)
    assert response.status_code == HTTPStatus.CONFLICT
    error = response.json()["error"]
    assert error["type"] == "conflict"
    assert error["code"] == "ARTIST_ALREADY_EXISTS"
    assert error["message"] == error_msg

    async with AsyncSessionLocal() as db:
        await db.delete(artist)
        await db.commit()
