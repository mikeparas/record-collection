import re
import uuid
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from src.core.exceptions import (
    ConflictException,
    NotFoundException,
    conflict_exception_handler,
    not_found_exception_handler,
    request_validation_error_handler,
)
from src.dependencies import get_artist_async_service, get_artist_service
from src.modules.artists.models import ArtistExtraModel, ArtistModel, Integrations
from src.modules.artists.router import router, router_v2
from src.modules.artists.service import (
    DEFAULT_LIST_LIMIT,
    ArtistAsyncService,
    ArtistService,
)
from src.shared.types import ArtistExtraData, DiscogsArtist
from tests.utils import assert_pagination, encode_cursor, generate_artists

app = FastAPI()
app.include_router(router)
app.include_router(router_v2)
app.add_exception_handler(NotFoundException, not_found_exception_handler)
app.add_exception_handler(RequestValidationError, request_validation_error_handler)
app.add_exception_handler(ConflictException, conflict_exception_handler)

client = TestClient(app)

BASE_PATH = router.prefix
BASE_PATH_ASYNC = router_v2.prefix


@pytest.fixture
def mock_artist_service():
    return MagicMock(spec=ArtistService)


@pytest.fixture
def mock_artist_async_service():
    return AsyncMock(spec=ArtistAsyncService)


@pytest_asyncio.fixture
async def async_client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


def test_get_artist_by_id_success(mock_artist_service: MagicMock):
    mock_artist = ArtistModel(name="Test Artist", sort_name="testartist")
    mock_artist.id = uuid.uuid4()

    mock_artist_service.get_by.return_value = mock_artist

    def override_artist_service():
        return mock_artist_service

    app.dependency_overrides[get_artist_service] = override_artist_service

    response = client.get(f"{BASE_PATH}/{mock_artist.id}")
    assert response.status_code == 200
    artist = response.json()
    assert artist["id"] == str(mock_artist.id)
    assert artist["name"] == mock_artist.name
    assert artist["sortName"] == mock_artist.sort_name

    mock_artist_service.get_by.assert_called_once_with(str(mock_artist.id))

    del app.dependency_overrides[get_artist_service]


def test_get_artist_by_name_success(mock_artist_service: MagicMock):
    mock_artist = ArtistModel(name="Test Artist", sort_name="testartist")
    mock_artist.id = uuid.uuid4()

    mock_artist_service.get_by.return_value = mock_artist

    def override_artist_service():
        return mock_artist_service

    app.dependency_overrides[get_artist_service] = override_artist_service

    response = client.get(f"{BASE_PATH}/{mock_artist.name}")
    assert response.status_code == 200
    artist = response.json()
    assert artist["id"] == str(mock_artist.id)
    assert artist["name"] == mock_artist.name
    assert artist["sortName"] == mock_artist.sort_name

    mock_artist_service.get_by.assert_called_once_with(mock_artist.name)

    del app.dependency_overrides[get_artist_service]


def test_get_artist_not_found(mock_artist_service: MagicMock):
    mock_artist_service.get_by.return_value = None

    def override_artist_service():
        return mock_artist_service

    app.dependency_overrides[get_artist_service] = override_artist_service

    name = "Not Found"
    response = client.get(f"{BASE_PATH}/{name}")
    assert response.status_code == 404
    body = response.json()
    error = body.get("error")
    assert error is not None
    assert error["type"] == "not_found"
    assert error["message"] == f"No artist found for {name}."
    assert error["code"] == "ARTIST_NOT_FOUND"

    mock_artist_service.get_by.assert_called_once_with(name)


def test_post_artist(mock_artist_service: MagicMock):
    mock_artist = ArtistModel(name="New Artist", sort_name="newartist")
    mock_artist.id = uuid.uuid4()

    mock_artist_service.create.return_value = mock_artist

    def override_artist_service():
        return mock_artist_service

    app.dependency_overrides[get_artist_service] = override_artist_service

    artist_data = {"name": mock_artist.name, "sortName": mock_artist.sort_name}
    response = client.post(BASE_PATH, json=artist_data)
    assert response.status_code == 201
    artist = response.json()
    assert artist["id"] == str(mock_artist.id)
    assert artist["name"] == mock_artist.name
    assert artist["sortName"] == mock_artist.sort_name

    headers = response.headers
    assert re.search(f"{BASE_PATH}/New Artist$", headers["Location"]) is not None

    mock_artist_service.create.assert_called_once_with(
        name=artist_data["name"], sort_name=artist_data["sortName"]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("req_headers", [{}, {"X-Correlation-ID": str(uuid.uuid4())}])
async def test_async_post_artist(
    req_headers: dict[str, Any],
    mock_artist_async_service: AsyncMock,
    async_client: AsyncClient,
):
    discogs_id = 12345
    mock_artist = ArtistModel(
        name="New Artist",
        sort_name="newartist",
        integrations=Integrations(discogs=discogs_id),
    )
    mock_artist.id = uuid.uuid4()

    mock_artist_async_service.create.return_value = mock_artist

    def override_artist_service():
        return mock_artist_async_service

    app.dependency_overrides[get_artist_async_service] = override_artist_service

    artist_data: dict[str, Any] = {
        "name": mock_artist.name,
        "sortName": mock_artist.sort_name,
        "integrations": {"discogs": discogs_id},
    }
    response = await async_client.post(
        BASE_PATH_ASYNC, json=artist_data, headers=req_headers
    )
    assert response.status_code == 201
    artist = response.json()
    assert artist["id"] == str(mock_artist.id)
    assert artist["name"] == mock_artist.name
    assert artist["sortName"] == mock_artist.sort_name
    assert (
        artist["integrations"] == Integrations.model_dump(mock_artist.integrations)
        if mock_artist.integrations is not None
        else None
    )

    resp_headers = response.headers
    assert (
        re.search(f"{BASE_PATH_ASYNC}/New Artist$", resp_headers["Location"])
        is not None
    )

    mock_artist_async_service.create.assert_called_once_with(
        name=mock_artist.name,
        sort_name=mock_artist.sort_name,
        integrations=Integrations(discogs=discogs_id),
        correlation_id=req_headers.get("X-Correlation-ID"),
    )


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
                    "code": "non_empty_string",
                    "message": "Must be a non-empty string value.",
                }
            ],
        ),
        (
            {"name": "string", "sortName": "   "},
            [
                {
                    "field": "sortName",
                    "code": "non_empty_string",
                    "message": "Must be a non-empty string value.",
                }
            ],
        ),
        (
            {"name": "", "sortName": ""},
            [
                {
                    "field": "name",
                    "code": "non_empty_string",
                    "message": "Must be a non-empty string value.",
                },
                {
                    "field": "sortName",
                    "code": "non_empty_string",
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
    assert response.status_code == 400
    error = response.json()["error"]
    print(f"{error=}")
    assert error["type"] == "validation_error"
    assert error["code"] == "ARTIST_VALIDATION_ERROR"
    assert error["message"] == "Artist data validation failed."
    assert len(error["details"]) == len(error_details)
    for d in error_details:
        assert d in error["details"]


@pytest.mark.asyncio
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
                    "code": "non_empty_string",
                    "message": "Must be a non-empty string value.",
                }
            ],
        ),
        (
            {"name": "string", "sortName": "   "},
            [
                {
                    "field": "sortName",
                    "code": "non_empty_string",
                    "message": "Must be a non-empty string value.",
                }
            ],
        ),
        (
            {"name": "", "sortName": ""},
            [
                {
                    "field": "name",
                    "code": "non_empty_string",
                    "message": "Must be a non-empty string value.",
                },
                {
                    "field": "sortName",
                    "code": "non_empty_string",
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
):
    response = await async_client.post(BASE_PATH_ASYNC, json=payload)
    assert response.status_code == 400
    error = response.json()["error"]
    print(f"{error=}")
    assert error["type"] == "validation_error"
    assert error["code"] == "ARTIST_VALIDATION_ERROR"
    assert error["message"] == "Artist data validation failed."
    assert len(error["details"]) == len(error_details)
    for d in error_details:
        assert d in error["details"]


def test_post_artist_duplicate(mock_artist_service: MagicMock):
    artist_data = {"name": "Duplicate Artist", "sortName": "duplicateartist"}

    mock_artist_service.create.side_effect = [
        ConflictException(
            code="ARTIST_ALREADY_EXISTS",
            message=f"An artist with name {artist_data['name']} already exists.",
        )
    ]

    def override_artist_service():
        return mock_artist_service

    app.dependency_overrides[get_artist_service] = override_artist_service  # type: ignore

    response = client.post(BASE_PATH, json=artist_data)
    assert response.status_code == HTTPStatus.CONFLICT
    error = response.json()["error"]
    assert error["type"] == "conflict"
    assert error["code"] == "ARTIST_ALREADY_EXISTS"
    assert (
        error["message"] == f"An artist with name {artist_data['name']} already exists."
    )

    mock_artist_service.create.assert_called_once_with(
        name=artist_data["name"], sort_name=artist_data["sortName"]
    )


@pytest.mark.asyncio
async def test_async_post_artist_duplicate(
    mock_artist_async_service: AsyncMock, async_client: AsyncClient
):
    artist_data = {"name": "Duplicate Artist", "sortName": "duplicateartist"}

    mock_artist_async_service.create.side_effect = [
        ConflictException(
            code="ARTIST_ALREADY_EXISTS",
            message=f"An artist with name {artist_data['name']} already exists.",
        )
    ]

    def override_artist_service():
        return mock_artist_async_service

    app.dependency_overrides[get_artist_async_service] = override_artist_service  # type: ignore

    response = await async_client.post(BASE_PATH_ASYNC, json=artist_data)
    assert response.status_code == HTTPStatus.CONFLICT
    error = response.json()["error"]
    assert error["type"] == "conflict"
    assert error["code"] == "ARTIST_ALREADY_EXISTS"
    assert (
        error["message"] == f"An artist with name {artist_data['name']} already exists."
    )

    mock_artist_async_service.create.assert_called_once_with(
        name=artist_data["name"],
        sort_name=artist_data["sortName"],
        integrations=None,
        correlation_id=None,
    )


def test_get_artists_list(mock_artist_service: MagicMock):
    mock_artists = generate_artists(DEFAULT_LIST_LIMIT)
    last_artist_id = mock_artists[-1].sort_name

    mock_artist_service.list.return_value = (mock_artists, last_artist_id)

    def overrider_artist_service():
        return mock_artist_service

    app.dependency_overrides[get_artist_service] = overrider_artist_service

    response = client.get(BASE_PATH)
    assert response.status_code == 200
    body = response.json()

    data = body.get("data")
    assert data is not None
    assert len(data) == DEFAULT_LIST_LIMIT

    last_sort_name = data[-1]["sortName"]
    assert_pagination(
        body, DEFAULT_LIST_LIMIT, encode_cursor(last_sort_name), BASE_PATH
    )

    mock_artist_service.list.assert_called_once_with(
        limit=DEFAULT_LIST_LIMIT, last_cursor=None
    )


def test_get_artists_list_empty(mock_artist_service: MagicMock):
    mock_artists: list[ArtistModel] = []

    mock_artist_service.list.return_value = (mock_artists, None)

    def overrider_artist_service():
        return mock_artist_service

    app.dependency_overrides[get_artist_service] = overrider_artist_service

    response = client.get(BASE_PATH)
    assert response.status_code == 200
    body = response.json()

    data = body.get("data")
    assert data is not None
    assert len(data) == 0

    assert_pagination(body, DEFAULT_LIST_LIMIT, None, BASE_PATH)

    mock_artist_service.list.assert_called_once_with(
        limit=DEFAULT_LIST_LIMIT, last_cursor=None
    )


def test_list_last_page(mock_artist_service: MagicMock):
    mock_artists = generate_artists(34)

    mock_artist_service.list.return_value = (mock_artists, None)

    def overrider_artist_service():
        return mock_artist_service

    app.dependency_overrides[get_artist_service] = overrider_artist_service

    response = client.get(BASE_PATH)
    assert response.status_code == 200
    body = response.json()

    data = body.get("data")
    assert data is not None
    assert len(data) == len(mock_artists)

    assert_pagination(body, DEFAULT_LIST_LIMIT, None, BASE_PATH)

    mock_artist_service.list.assert_called_once_with(
        limit=DEFAULT_LIST_LIMIT, last_cursor=None
    )


def test_get_artists_list_limit(mock_artist_service: MagicMock):
    limit = 25
    mock_artists = generate_artists(limit)
    last_artist_id = mock_artists[limit - 1].sort_name

    mock_artist_service.list.return_value = (mock_artists, last_artist_id)

    def overrider_artist_service():
        return mock_artist_service

    app.dependency_overrides[get_artist_service] = overrider_artist_service

    response = client.get(BASE_PATH, params={"limit": limit})
    assert response.status_code == 200
    body = response.json()

    data = body.get("data")
    assert data is not None
    assert len(data) == limit

    last_sort_name = data[-1]["sortName"]
    assert_pagination(body, limit, encode_cursor(last_sort_name), BASE_PATH)

    mock_artist_service.list.assert_called_once_with(limit=limit, last_cursor=None)


def test_get_artists_list_cursor(mock_artist_service: MagicMock):
    mock_artists = generate_artists(DEFAULT_LIST_LIMIT)
    last_artist_id = mock_artists[DEFAULT_LIST_LIMIT - 1].sort_name
    cursor = "lastsortname"
    token = encode_cursor(cursor)

    mock_artist_service.list.return_value = (mock_artists, last_artist_id)

    def overrider_artist_service():
        return mock_artist_service

    app.dependency_overrides[get_artist_service] = overrider_artist_service

    response = client.get(BASE_PATH, params={"cursor": token})
    assert response.status_code == 200
    body = response.json()

    data = body.get("data")
    assert data is not None
    assert len(data) == DEFAULT_LIST_LIMIT

    last_sort_name = data[-1]["sortName"]
    assert_pagination(
        body, DEFAULT_LIST_LIMIT, encode_cursor(last_sort_name), BASE_PATH
    )

    mock_artist_service.list.assert_called_once_with(
        limit=DEFAULT_LIST_LIMIT, last_cursor=cursor
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "id_, name, id_attr",
    [
        (uuid.uuid4(), "Test Artist", "id"),
        (uuid.uuid4(), "Test Artist", "name"),
    ],
)
async def test_async_get_artists_single_success(
    id_: uuid.UUID,
    name: str,
    id_attr: str,
    mock_artist_async_service: AsyncMock,
    async_client: AsyncClient,
):
    mock_artist = ArtistModel(name=name, sort_name="testartist")
    mock_artist.id = id_

    artist_extra = ArtistExtraModel(
        id=id_,
        data=ArtistExtraData(
            discogs=DiscogsArtist(
                id=12345,
                name=name,
                url="https://discogs.com/artist/12345",
                images=["https://img.discogs.com/abc.jpg"],
            )
        ),
    )
    mock_artist.extra = artist_extra

    mock_artist_async_service.get_by.return_value = mock_artist

    def override_artist_service():
        return mock_artist_async_service

    app.dependency_overrides[get_artist_async_service] = override_artist_service

    path_id = mock_artist.id if id_attr == "id" else mock_artist.name
    response = await async_client.get(f"{BASE_PATH_ASYNC}/{path_id}")
    assert response.status_code == 200
    artist = response.json()
    assert artist["id"] == str(mock_artist.id)
    assert artist["name"] == mock_artist.name
    assert artist["sortName"] == mock_artist.sort_name
    assert artist["integrations"] is None
    assert (
        artist_extra.data is not None
        and artist["extra"] == artist_extra.data.model_dump()
    )

    expected_call_arg = str(path_id)
    mock_artist_async_service.get_by.assert_called_once_with(expected_call_arg)

    del app.dependency_overrides[get_artist_async_service]


@pytest.mark.asyncio
async def test_async_get_artist_not_found(
    mock_artist_async_service: AsyncMock, async_client: AsyncClient
):
    mock_artist_async_service.get_by.return_value = None

    def override_artist_service():
        return mock_artist_async_service

    app.dependency_overrides[get_artist_async_service] = override_artist_service

    name = "Not Found"
    response = await async_client.get(f"{BASE_PATH_ASYNC}/{name}")
    assert response.status_code == 404
    body = response.json()
    error = body.get("error")
    assert error is not None
    assert error["type"] == "not_found"
    assert error["message"] == f"No artist found for {name}."
    assert error["code"] == "ARTIST_NOT_FOUND"

    mock_artist_async_service.get_by.assert_called_once_with(name)
