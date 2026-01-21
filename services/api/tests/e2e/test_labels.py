import re
from http import HTTPStatus
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from src.core.database import SessionLocal
from src.main import app
from src.modules.labels.models import LabelModel
from src.modules.labels.service import DEFAULT_LIST_LIMIT
from tests.utils import assert_pagination, encode_cursor, generate_labels

# load_dotenv(".env.test")

pytestmark = pytest.mark.e2e

client = TestClient(app)

BASE_PATH = "/labels"


# @pytest.fixture(scope="module", autouse=True)
# def setup_db():
#     init_db(os.getenv("DATABASE_URL", ""))


@pytest.fixture(scope="module")
def seed_labels():
    mock_labels = generate_labels(58, True)

    db = SessionLocal()
    for mock_label in mock_labels:
        db.add(mock_label)
    db.commit()

    yield mock_labels

    for mock_label in mock_labels:
        db.delete(mock_label)
    db.commit()


def test_get_label_by_id():
    db = SessionLocal()
    label = LabelModel(name="Test Label", sort_name="testlabel")
    db.add(label)
    db.commit()

    response = client.get(f"{BASE_PATH}/{label.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(label.id)
    assert data["name"] == label.name
    assert data["sortName"] == label.sort_name

    # clean up
    db.delete(label)
    db.commit()

    db.close()


def test_get_label_by_name():
    db = SessionLocal()
    label = LabelModel(name="Test Label", sort_name="testlabel")
    db.add(label)
    db.commit()

    response = client.get(f"{BASE_PATH}/{label.name}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(label.id)
    assert data["name"] == label.name
    assert data["sortName"] == label.sort_name

    # clean up
    db.delete(label)
    db.commit()

    db.close()


def test_get_label_not_found():
    # nothing to seed
    name = "Not Found Label"

    response = client.get(f"{BASE_PATH}/{name}")
    assert response.status_code == 404
    body = response.json()
    assert body["detail"] == f"No label found for {name}."


def test_post_label_success():
    label_data = {"name": "New Label", "sortName": "newlabel"}

    response = client.post(BASE_PATH, json=label_data)
    assert response.status_code == HTTPStatus.CREATED
    label = response.json()
    assert label["name"] == label_data["name"]
    assert label["sortName"] == label_data["sortName"]
    assert label["id"] is not None

    headers = response.headers
    assert re.search(f"{BASE_PATH}/New Label$", headers["Location"]) is not None

    # check database
    db = SessionLocal()
    stmt = select(LabelModel).where(LabelModel.name == label_data["name"])
    result = db.scalars(stmt)
    db_label = result.one_or_none()
    assert db_label is not None
    assert label["id"] == str(db_label.id)

    db.delete(db_label)
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


@pytest.mark.parametrize(
    "payload,error_msg",
    [
        (
            {"name": "Test Label", "sortName": "newtestlabel"},
            "A label with name Test Label already exists.",
        ),
        (
            {"name": "New Test Label", "sortName": "testlabel"},
            "A label with sortName testlabel already exists.",
        ),
    ],
)
def test_post_label_duplicate(payload: dict[str, str], error_msg: str):
    # seed artist
    db = SessionLocal()
    label = LabelModel(name="Test Label", sort_name="testlabel")
    db.add(label)
    db.commit()

    response = client.post(BASE_PATH, json=payload)
    assert response.status_code == HTTPStatus.CONFLICT
    error = response.json()["error"]
    assert error["type"] == "conflict"
    assert error["code"] == "LABEL_ALREADY_EXISTS"
    assert error["message"] == error_msg

    # clean up seed
    db.delete(label)
    db.commit()

    db.close()


def test_get_labels_list(seed_labels: list[LabelModel]):
    expected_limit = DEFAULT_LIST_LIMIT
    expected_first_name = "Label 01"
    expected_first_sort_name = "label01"

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


def test_get_labels_list_limit(seed_labels: list[LabelModel]):
    expected_limit = 25
    expected_first_name = "Label 01"
    expected_first_sort_name = "label01"

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
def test_get_labels_list_cursor(
    limit: int, start_idx: int, seed_labels: list[LabelModel]
):
    expected_limit = limit

    cursor_sort_name = seed_labels[start_idx - 1].sort_name
    token = encode_cursor(cursor_sort_name)

    expected_first_name = seed_labels[start_idx].name
    expected_first_sort_name = seed_labels[start_idx].sort_name

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


def test_get_labels_list_last_page(seed_labels: list[LabelModel]):
    idx = 50
    cursor = encode_cursor(seed_labels[idx].sort_name)

    expected_limit = DEFAULT_LIST_LIMIT
    expected_first_name = seed_labels[idx + 1].name
    expected_first_sort_name = seed_labels[idx + 1].sort_name

    response = client.get(BASE_PATH, params={"cursor": cursor})
    assert response.status_code == HTTPStatus.OK
    body = response.json()

    data = body.get("data")
    assert data is not None
    assert len(data) == len(seed_labels) - idx - 1
    assert data[0]["name"] == expected_first_name
    assert data[0]["sortName"] == expected_first_sort_name

    assert_pagination(body, expected_limit, None, BASE_PATH)
