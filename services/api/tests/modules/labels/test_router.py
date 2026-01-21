import re
import uuid
from http import HTTPStatus
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from src.core.exceptions import (
    ConflictException,
    NotFoundException,
    conflict_exception_handler,
    not_found_exception_handler,
    request_validation_error_handler,
)
from src.dependencies import get_label_service
from src.modules.labels.models import LabelModel
from src.modules.labels.router import router
from src.modules.labels.service import DEFAULT_LIST_LIMIT, LabelService
from tests.utils import assert_pagination, encode_cursor, generate_labels

app = FastAPI()
app.include_router(router)
app.add_exception_handler(NotFoundException, not_found_exception_handler)
app.add_exception_handler(RequestValidationError, request_validation_error_handler)
app.add_exception_handler(ConflictException, conflict_exception_handler)

client = TestClient(app)

BASE_PATH = "/labels"


@pytest.fixture
def mock_label_service():
    return MagicMock(spec=LabelService)


def test_get_label_by_id_success(mock_label_service: MagicMock):
    mock_label = LabelModel(name="Test Label", sort_name="testlabel")
    mock_label.id = uuid.uuid4()

    mock_label_service.get_by.return_value = mock_label

    def override_label_service():
        return mock_label_service

    app.dependency_overrides[get_label_service] = override_label_service

    response = client.get(f"{BASE_PATH}/{mock_label.id}")
    assert response.status_code == 200
    label = response.json()
    assert label["id"] == str(mock_label.id)
    assert label["name"] == mock_label.name
    assert label["sortName"] == mock_label.sort_name

    mock_label_service.get_by.assert_called_once_with(str(mock_label.id))

    del app.dependency_overrides[get_label_service]


def test_get_label_by_name_success(mock_label_service: MagicMock):
    mock_label = LabelModel(name="Test Label", sort_name="testlabel")
    mock_label.id = uuid.uuid4()

    mock_label_service.get_by.return_value = mock_label

    def override_label_service():
        return mock_label_service

    app.dependency_overrides[get_label_service] = override_label_service

    response = client.get(f"{BASE_PATH}/{mock_label.name}")
    assert response.status_code == 200
    label = response.json()
    assert label["id"] == str(mock_label.id)
    assert label["name"] == mock_label.name
    assert label["sortName"] == mock_label.sort_name

    mock_label_service.get_by.assert_called_once_with(mock_label.name)

    del app.dependency_overrides[get_label_service]


def test_get_label_not_found(mock_label_service: MagicMock):
    mock_label_service.get_by.return_value = None

    def override_label_service():
        return mock_label_service

    app.dependency_overrides[get_label_service] = override_label_service

    name = "Not Found Label"
    response = client.get(f"{BASE_PATH}/{name}")
    assert response.status_code == 404
    body = response.json()
    assert body["detail"] == f"No label found for {name}."


def test_post_label(mock_label_service: MagicMock):
    mock_label = LabelModel(name="New Label", sort_name="newlabel")
    mock_label.id = uuid.uuid4()

    mock_label_service.create.return_value = mock_label

    def override_label_service():
        return mock_label_service

    app.dependency_overrides[get_label_service] = override_label_service

    label_data = {"name": mock_label.name, "sortName": mock_label.sort_name}
    response = client.post(BASE_PATH, json=label_data)
    assert response.status_code == 201
    label = response.json()
    assert label["id"] == str(mock_label.id)
    assert label["name"] == mock_label.name
    assert label["sortName"] == mock_label.sort_name

    headers = response.headers
    assert re.search("/labels/New Label$", headers["Location"]) is not None


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
def test_post_label_validation(
    payload: dict[str, Any], error_details: list[dict[str, str]]
):
    response = client.post(BASE_PATH, json=payload)
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["type"] == "validation_error"
    assert error["code"] == "LABEL_VALIDATION_ERROR"
    assert error["message"] == "Label data validation failed."
    assert len(error["details"]) == len(error_details)
    for d in error_details:
        assert d in error_details


def test_post_label_duplicate(mock_label_service: MagicMock):
    label_data = {"name": "Duplicate Label", "sortName": "duplicatelabel"}

    mock_label_service.create.side_effect = [
        ConflictException(
            code="LABEL_ALREADY_EXISTS",
            message=f"A label with name {label_data['name']} already exists.",
        )
    ]

    def override_label_service():
        return mock_label_service

    app.dependency_overrides[get_label_service] = override_label_service  # type: ignore

    response = client.post(BASE_PATH, json=label_data)
    assert response.status_code == HTTPStatus.CONFLICT
    error = response.json()["error"]
    assert error["type"] == "conflict"
    assert error["code"] == "LABEL_ALREADY_EXISTS"
    assert error["message"] == f"A label with name {label_data['name']} already exists."


def test_get_labels_list(mock_label_service: MagicMock):
    mock_labels = generate_labels(DEFAULT_LIST_LIMIT)
    last_label_id = mock_labels[-1].sort_name

    mock_label_service.list.return_value = (mock_labels, last_label_id)

    def overrider_label_service():
        return mock_label_service

    app.dependency_overrides[get_label_service] = overrider_label_service

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

    mock_label_service.list.assert_called_once_with(
        limit=DEFAULT_LIST_LIMIT, last_cursor=None
    )


def test_get_labels_list_limit(mock_label_service: MagicMock):
    limit = 25
    mock_labels = generate_labels(limit)
    last_label_id = mock_labels[limit - 1].sort_name

    mock_label_service.list.return_value = (mock_labels, last_label_id)

    def override_label_service():
        return mock_label_service

    app.dependency_overrides[get_label_service] = override_label_service

    response = client.get(BASE_PATH, params={"limit": limit})
    assert response.status_code == 200
    body = response.json()

    data = body.get("data")
    assert data is not None
    assert len(data) == limit

    last_sort_name = data[-1]["sortName"]
    assert_pagination(body, limit, encode_cursor(last_sort_name), BASE_PATH)

    mock_label_service.list.assert_called_once_with(limit=limit, last_cursor=None)


def test_get_labels_list_cursor(mock_label_service: MagicMock):
    mock_labels = generate_labels(DEFAULT_LIST_LIMIT)
    last_label_id = mock_labels[DEFAULT_LIST_LIMIT - 1].sort_name
    cursor = "lastsortname"
    token = encode_cursor(cursor)

    mock_label_service.list.return_value = (mock_labels, last_label_id)

    def override_label_service():
        return mock_label_service

    app.dependency_overrides[get_label_service] = override_label_service

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

    mock_label_service.list.assert_called_once_with(
        limit=DEFAULT_LIST_LIMIT, last_cursor=cursor
    )


def test_list_last_page(mock_label_service: MagicMock):
    mock_labels = generate_labels(34)

    mock_label_service.list.return_value = (mock_labels, None)

    def override_label_service():
        return mock_label_service

    app.dependency_overrides[get_label_service] = override_label_service

    response = client.get(BASE_PATH)
    assert response.status_code == 200
    body = response.json()

    data = body.get("data")
    assert data is not None
    assert len(data) == len(mock_labels)

    assert_pagination(body, DEFAULT_LIST_LIMIT, None, BASE_PATH)

    mock_label_service.list.assert_called_once_with(
        limit=DEFAULT_LIST_LIMIT, last_cursor=None
    )


def test_get_labels_list_empty(mock_label_service: MagicMock):
    mock_labels: list[LabelModel] = []

    mock_label_service.list.return_value = (mock_labels, None)

    def override_label_service():
        return mock_label_service

    app.dependency_overrides[get_label_service] = override_label_service

    response = client.get(BASE_PATH)
    assert response.status_code == 200
    body = response.json()

    data = body.get("data")
    assert data is not None
    assert len(data) == 0

    assert_pagination(body, DEFAULT_LIST_LIMIT, None, BASE_PATH)

    mock_label_service.list.assert_called_once_with(
        limit=DEFAULT_LIST_LIMIT, last_cursor=None
    )
