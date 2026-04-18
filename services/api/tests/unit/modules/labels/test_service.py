import uuid
from collections.abc import Callable, Sequence
from typing import Any, Protocol, TypeVar, cast
from unittest.mock import MagicMock, Mock

import pytest
from psycopg import errors
from sqlalchemy import Select, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError

from src.core.exceptions import ConflictException
from src.modules.labels.models import LabelModel
from src.modules.labels.service import DEFAULT_LIST_LIMIT, LabelService
from tests.utils import generate_labels

T = TypeVar("T", bound=LabelModel)


class ScalarsResultProtocol(Protocol[T]):
    # def one_or_none(self) -> T | None: ...
    one_or_none: Callable[[], T | None]
    all: Callable[[], Sequence[T]]


class MockedSession(Protocol):
    scalars: Callable[[Any], ScalarsResultProtocol[LabelModel]]
    add: Callable[[LabelModel], None]
    commit: Callable[[], None]


def compile_statement(stmt: Select[Any]) -> str:
    return str(
        stmt.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )


def test_get_by_id():
    mock_id = uuid.uuid4()
    mock_label = LabelModel(name="Test Label", sort_name="testlabel")
    mock_label.id = mock_id

    mock_session = MagicMock()
    typed_mock_session = cast(MockedSession, mock_session)
    scalars_mock = typed_mock_session.scalars.return_value
    scalars_mock.one_or_none.return_value = mock_label

    label_service = LabelService(mock_session)
    label = label_service.get_by(str(mock_id))
    assert label is not None
    assert label.id == mock_id
    assert label.name == mock_label.name
    assert label.sort_name == mock_label.sort_name

    stmt = select(LabelModel).where(LabelModel.id == mock_id)
    arg_stmt = typed_mock_session.scalars.call_args[0][0]
    assert compile_statement(stmt) == compile_statement(arg_stmt)


def test_get_by_name():
    mock_id = uuid.uuid4()
    mock_label = LabelModel(name="Test Label", sort_name="testlabel")
    mock_label.id = mock_id

    mock_session = MagicMock()
    typed_mock_session = cast(MockedSession, mock_session)
    scalars_mock = typed_mock_session.scalars.return_value
    scalars_mock.one_or_none.return_value = mock_label

    label_service = LabelService(mock_session)
    label = label_service.get_by(mock_label.name)
    assert label is not None
    assert label.id == mock_id
    assert label.name == mock_label.name
    assert label.sort_name == mock_label.sort_name

    stmt = select(LabelModel).where(LabelModel.name == mock_label.name)
    arg_stmt = typed_mock_session.scalars.call_args[0][0]
    assert compile_statement(stmt) == compile_statement(arg_stmt)


def test_get_by_not_found():
    mock_session = MagicMock()
    typed_mock_session = cast(MockedSession, mock_session)
    scalars_mock = typed_mock_session.scalars.return_value  # type: ignore
    scalars_mock.one_or_none.return_value = None  # type: ignore

    label_service = LabelService(mock_session)
    label = label_service.get_by("Not Found")
    assert label is None


def test_create():
    mock_session = MagicMock()
    typed_mock_session = cast(MockedSession, mock_session)

    mock_id = uuid.uuid4()

    def mock_add(instance: LabelModel):
        instance.id = mock_id

    typed_mock_session.add.side_effect = mock_add

    name = "New Label"
    sort_name = "newlabel"

    label_service = LabelService(mock_session)
    label = label_service.create(name=name, sort_name=sort_name)
    assert label.id == mock_id
    assert label.name == name
    assert label.sort_name == sort_name

    add_arg = mock_session.add.call_args[0][0]
    assert isinstance(add_arg, LabelModel)
    assert add_arg.name == name
    assert add_arg.sort_name == sort_name


@pytest.mark.parametrize(
    "constraint,error_msg",
    [
        # adjust error messages with artist data in the test
        ("UQ_labels_name", "A label with name Duplicate Label already exists."),
        (
            "UQ_labels_sort_name",
            "A label with sortName duplicatelabel already exists.",
        ),
    ],
)
def test_create_duplicate(constraint: str, error_msg: str):
    mock_session = MagicMock()
    typed_mock_session = cast(MockedSession, mock_session)

    # mock psycopg error
    orig_error = Mock(spec=errors.UniqueViolation)
    orig_error.diag = Mock()  # type: ignore
    orig_error.diag.constraint_name = constraint
    orig_error.diag.table_name = "labels"
    orig_error.diag.schema_name = "public"

    # mock IntegrityError
    integrity_error = IntegrityError(
        statement="insert statement", params={}, orig=orig_error
    )

    typed_mock_session.add = Mock()
    typed_mock_session.commit = Mock()
    typed_mock_session.commit.side_effect = integrity_error

    name = "Duplicate Label"
    sort_name = "duplicatelabel"

    label_service = LabelService(mock_session)
    with pytest.raises(ConflictException) as exc:
        label_service.create(name=name, sort_name=sort_name)

    assert exc.value.code == "LABEL_ALREADY_EXISTS"
    assert exc.value.message == error_msg


def test_list():
    mock_session = MagicMock()
    typed_mock_session = cast(MockedSession, mock_session)

    mock_labels = generate_labels(DEFAULT_LIST_LIMIT + 1)
    typed_mock_session.scalars = Mock()
    typed_mock_session.scalars.return_value.all = Mock()
    typed_mock_session.scalars.return_value.all.return_value = mock_labels

    label_service = LabelService(mock_session)
    labels, last_sort_name = label_service.list(
        limit=DEFAULT_LIST_LIMIT, last_cursor=None
    )
    assert len(labels) == DEFAULT_LIST_LIMIT
    assert last_sort_name == mock_labels[-2].sort_name

    stmt = (
        select(LabelModel).order_by(LabelModel.sort_name).limit(DEFAULT_LIST_LIMIT + 1)
    )
    arg_stmt = typed_mock_session.scalars.call_args[0][0]
    assert compile_statement(stmt) == compile_statement(arg_stmt)


def test_list_last_cursor():
    mock_session = MagicMock()
    typed_mock_session = cast(MockedSession, mock_session)
    typed_mock_session.scalars = Mock()
    typed_mock_session.scalars.return_value.all = Mock()

    mock_labels = generate_labels(DEFAULT_LIST_LIMIT + 1)
    typed_mock_session.scalars.return_value.all.return_value = mock_labels

    cursor = "lastsortname"

    label_service = LabelService(mock_session)
    labels, last_sort_name = label_service.list(
        limit=DEFAULT_LIST_LIMIT, last_cursor=cursor
    )
    assert len(labels) == DEFAULT_LIST_LIMIT
    assert last_sort_name == mock_labels[-2].sort_name

    stmt = (
        select(LabelModel)
        .where(LabelModel.sort_name > cursor)
        .order_by(LabelModel.sort_name)
        .limit(DEFAULT_LIST_LIMIT + 1)
    )
    arg_stmt = typed_mock_session.scalars.call_args[0][0]
    assert compile_statement(stmt) == compile_statement(arg_stmt)


def test_list_last_page():
    mock_session = MagicMock()
    typed_mock_session = cast(MockedSession, mock_session)
    typed_mock_session.scalars = Mock()
    typed_mock_session.scalars.return_value.all = Mock()

    mock_labels = generate_labels(50)
    typed_mock_session.scalars.return_value.all.return_value = mock_labels

    label_service = LabelService(mock_session)
    labels, last_sort_name = label_service.list(
        limit=DEFAULT_LIST_LIMIT, last_cursor=None
    )
    assert len(labels) == DEFAULT_LIST_LIMIT
    assert last_sort_name is None

    stmt = (
        select(LabelModel).order_by(LabelModel.sort_name).limit(DEFAULT_LIST_LIMIT + 1)
    )
    arg_stmt = typed_mock_session.scalars.call_args[0][0]
    assert compile_statement(stmt) == compile_statement(arg_stmt)


def test_list_empty():
    mock_session = MagicMock()
    typed_mock_session = cast(MockedSession, mock_session)
    typed_mock_session.scalars = Mock()
    typed_mock_session.scalars.return_value.all = Mock()

    mock_artists = []
    typed_mock_session.scalars.return_value.all.return_value = mock_artists

    label_service = LabelService(mock_session)
    labels, last_sort_name = label_service.list(
        limit=DEFAULT_LIST_LIMIT, last_cursor=None
    )
    assert len(labels) == 0
    assert last_sort_name is None

    stmt = (
        select(LabelModel).order_by(LabelModel.sort_name).limit(DEFAULT_LIST_LIMIT + 1)
    )
    arg_stmt = typed_mock_session.scalars.call_args[0][0]
    assert compile_statement(stmt) == compile_statement(arg_stmt)
