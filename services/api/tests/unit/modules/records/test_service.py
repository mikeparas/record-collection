import uuid
from typing import Any, Protocol, TypeVar, cast
from unittest.mock import MagicMock, Mock

import pytest
from fastapi.exceptions import RequestValidationError
from sqlalchemy import Select, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import selectinload

from src.modules.artists.models import ArtistModel
from src.modules.labels.models import LabelModel
from src.modules.records.models import RecordData, RecordModel
from src.modules.records.service import (
    DEFAULT_LIST_LIMIT,
    RecordService,
    RecordSortOption,
)
from tests.utils import generate_records

T = TypeVar("T", bound=RecordModel, covariant=True)


class ScalarsResultProtocol(Protocol[T]):
    def one_or_none(self) -> T | None: ...


class MockedSession(Protocol):
    def scalars(self, statement: Any) -> ScalarsResultProtocol[RecordModel]: ...
    def add(self, instance: RecordModel): ...
    def commit(self): ...


def compile_statement(stmt: Select[Any]) -> str:
    return str(
        stmt.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )


def assert_list_item(expected: RecordModel, received: RecordModel):
    assert received.id == expected.id
    assert received.title == expected.title
    assert received.format_ == expected.format_
    assert received.year_release == expected.year_release
    assert received.year_pressing == expected.year_pressing
    assert received.data.color == expected.data.color
    assert received.data.notes == expected.data.notes
    assert received.artists == expected.artists
    assert received.labels == expected.labels


def assert_artist_label_scalars(
    mock_scalars: Mock, artist_id: uuid.UUID, label_id: uuid.UUID
):
    # assumes one artist and one label lookup
    artist_select = select(ArtistModel).where(ArtistModel.id == artist_id)
    artist_scalars_arg = mock_scalars.call_args_list[0].args
    assert compile_statement(artist_select) == compile_statement(artist_scalars_arg[0])

    label_select = select(LabelModel).where(LabelModel.id == label_id)
    label_scalars_arg = mock_scalars.call_args_list[1].args
    assert compile_statement(label_select) == compile_statement(label_scalars_arg[0])


def test_get_by():
    mock_artist = ArtistModel(name="Test Artist", sort_name="testartist")
    mock_artist.id = uuid.uuid4()

    mock_label = LabelModel(name="Test Label", sort_name="testlabel")
    mock_label.id = uuid.uuid4()

    mock_record = RecordModel(
        title="Test Record",
        format_="LP",
        year_release=2025,
        year_pressing=2025,
        data=RecordData(color="Black vinyl", notes="None"),
        artists=[mock_artist],
        labels=[mock_label],
        sk_artist_year="sk_artist_year",
        sk_artist_title="sk_artist_title",
        sk_label_artist_year="sk_label_artist_year",
        sk_label_year_artist="sk_label_year_artist",
    )
    mock_record.id = uuid.uuid4()

    mock_session = MagicMock()
    typed_mock_session = cast(MockedSession, mock_session)
    typed_mock_session.scalars = Mock()
    scalars_mock = typed_mock_session.scalars.return_value
    scalars_mock.one_or_none = Mock()
    scalars_mock.one_or_none.return_value = mock_record

    record_service = RecordService(mock_session)
    record_item = record_service.get_by(mock_record.id)
    assert record_item is not None
    assert record_item.id == mock_record.id
    assert record_item.title == mock_record.title
    assert record_item.format_ == mock_record.format_
    assert record_item.year_release == mock_record.year_release
    assert record_item.year_pressing == mock_record.year_pressing
    assert record_item.data.color == mock_record.data.color
    assert record_item.data.notes == mock_record.data.notes
    assert record_item.artists == [mock_artist]
    assert record_item.labels == [mock_label]

    typed_mock_session.scalars.assert_called_once()
    scalars_mock.one_or_none.assert_called_once()

    arg_stmt = cast(Select, typed_mock_session.scalars.call_args[0][0])  # type: ignore
    assert arg_stmt.whereclause is not None
    assert arg_stmt.whereclause.compare(RecordModel.id == mock_record.id)

    stmt = (
        select(RecordModel)
        .where(RecordModel.id == mock_record.id)
        .options(selectinload(RecordModel.artists), selectinload(RecordModel.labels))
    )
    assert compile_statement(stmt) == compile_statement(arg_stmt)

    # TODO: possibly test loading strategy?


def test_create_success():
    mock_session = MagicMock()
    typed_mock_session = cast(MockedSession, mock_session)

    mock_artist = ArtistModel(name="Test Artist", sort_name="testartist")
    mock_artist.id = uuid.uuid4()

    mock_label = LabelModel(name="Test Label", sort_name="testlabel")
    mock_label.id = uuid.uuid4()

    mock_id = uuid.uuid4()

    def mock_add(instance: RecordModel):
        instance.id = mock_id

    typed_mock_session.add = Mock()
    typed_mock_session.add.side_effect = mock_add
    typed_mock_session.commit = Mock()

    typed_mock_session.scalars = Mock()
    typed_mock_session.scalars.return_value.one_or_none.side_effect = [
        mock_artist,
        mock_label,
    ]

    mock_record = RecordModel(
        title="Test Record",
        format_="LP",
        year_release=2025,
        year_pressing=2025,
        data=RecordData(color="Black vinyl", notes="Last show cover"),
        artists=[mock_artist],
        labels=[mock_label],
        sk_artist_year="sk_artist_year",
        sk_artist_title="sk_artist_title",
        sk_label_artist_year="sk_label_artist_year",
        sk_label_year_artist="sk_label_year_artist",
    )

    record_service = RecordService(mock_session)
    record_item = record_service.create(
        title=mock_record.title,
        format_=mock_record.format_,
        year_release=mock_record.year_release,
        year_pressing=mock_record.year_pressing,
        data=mock_record.data,
        artist_ids=[mock_artist.id],
        label_ids=[mock_label.id],
        sk_artist_year=mock_record.sk_artist_year,
        sk_artist_title=mock_record.sk_artist_title,
        sk_label_artist_year=mock_record.sk_label_artist_year,
        sk_label_year_artist=mock_record.sk_label_year_artist,
    )

    assert record_item.id == mock_id
    assert record_item.title == mock_record.title
    assert record_item.format_ == mock_record.format_
    assert record_item.year_release == mock_record.year_release
    assert record_item.year_pressing == mock_record.year_pressing
    assert record_item.data == mock_record.data
    assert record_item.artists == [mock_artist]
    assert record_item.labels == [mock_label]

    mock_scalars = cast(Mock, mock_session.scalars)
    assert_artist_label_scalars(mock_scalars, mock_artist.id, mock_label.id)

    typed_mock_session.add.assert_called_once()
    typed_mock_session.commit.assert_called_once()

    add_arg = mock_session.add.call_args[0][0]
    assert isinstance(add_arg, RecordModel)
    assert add_arg.title == mock_record.title
    assert add_arg.format_ == mock_record.format_
    assert add_arg.year_release == mock_record.year_release
    assert add_arg.year_pressing == mock_record.year_pressing
    assert add_arg.data == add_arg.data
    assert add_arg.artists == [mock_artist]
    assert add_arg.labels == [mock_label]
    assert add_arg.sk_artist_year == mock_record.sk_artist_year
    assert add_arg.sk_artist_title == mock_record.sk_artist_title
    assert add_arg.sk_label_artist_year == mock_record.sk_label_artist_year
    assert add_arg.sk_label_year_artist == mock_record.sk_label_year_artist


def test_create_missing_relationship():
    mock_session = MagicMock()
    typed_mock_session = cast(MockedSession, mock_session)

    typed_mock_session.scalars.return_value.one_or_none.side_effect = [None, None]

    missing_artist_id = uuid.uuid4()
    missing_label_id = uuid.uuid4()

    record_service = RecordService(mock_session)

    with pytest.raises(RequestValidationError) as exc:
        record_service.create(
            title="Test Title",
            format_="LP",
            year_release=2025,
            year_pressing=2025,
            data=RecordData(color="Black vinyl"),
            artist_ids=[missing_artist_id],
            label_ids=[missing_label_id],
            sk_artist_year="sk_artist_year",
            sk_artist_title="sk_artist_title",
            sk_label_artist_year="sk_label_artist_year",
            sk_label_year_artist="sk_label_year_artist",
        )

    assert any(
        [
            (
                e["loc"] == ["body", "artists"]
                and e["type"] == "invalid_reference"
                and e["msg"] == f"Artists not found [{missing_artist_id}]"
            )
            for e in exc.value.errors()
        ]
    )
    assert any(
        [
            (
                e["loc"] == ["body", "labels"]
                and e["type"] == "invalid_reference"
                and e["msg"] == f"Labels not found [{missing_label_id}]"
            )
            for e in exc.value.errors()
        ]
    )

    mock_scalars = cast(Mock, mock_session.scalars)
    assert_artist_label_scalars(mock_scalars, missing_artist_id, missing_label_id)


def test_list():
    mock_records, _, _ = generate_records(DEFAULT_LIST_LIMIT + 1)
    sorted_mock_records = sorted(mock_records, key=lambda r: r.sk_artist_year)

    mock_session = MagicMock()
    typed_mock_session = cast(MockedSession, mock_session)
    typed_mock_session.scalars = Mock()
    scalars_mock = typed_mock_session.scalars.return_value
    scalars_mock.all = Mock()
    scalars_mock.all.return_value = sorted_mock_records

    record_service = RecordService(mock_session)
    records, last_sort_key = record_service.list(
        limit=DEFAULT_LIST_LIMIT,
        sort_key_name=RecordSortOption.ARTIST_YEAR,
        last_cursor=None,
    )

    assert len(records) == DEFAULT_LIST_LIMIT
    assert last_sort_key == sorted_mock_records[-2].sk_artist_year

    # check order
    assert records[0].id == sorted_mock_records[0].id
    assert records[-1].id == sorted_mock_records[-2].id

    # check one record
    assert_list_item(sorted_mock_records[0], records[0])

    typed_mock_session.scalars.assert_called_once()
    scalars_mock.all.assert_called_once()

    arg_stmt = cast(Select, typed_mock_session.scalars.call_args[0][0])  # type: ignore
    assert arg_stmt.whereclause is None

    stmt = (
        select(RecordModel)
        .limit(DEFAULT_LIST_LIMIT + 1)
        .order_by(RecordModel.sk_artist_year)
        .options(selectinload(RecordModel.artists), selectinload(RecordModel.labels))
    )
    assert compile_statement(stmt) == compile_statement(arg_stmt)


def test_list_last_cursor():
    mock_records, _, _ = generate_records(DEFAULT_LIST_LIMIT + 1)
    sorted_mock_records = sorted(mock_records, key=lambda r: r.sk_artist_year)

    mock_session = MagicMock()
    typed_mock_session = cast(MockedSession, mock_session)
    typed_mock_session.scalars = Mock()
    scalars_mock = typed_mock_session.scalars.return_value
    scalars_mock.all = Mock()
    scalars_mock.all.return_value = sorted_mock_records

    cursor = "lastsortkey"

    record_service = RecordService(mock_session)
    records, last_sort_key = record_service.list(
        limit=DEFAULT_LIST_LIMIT,
        last_cursor=cursor,
        sort_key_name=RecordSortOption.ARTIST_YEAR,
    )
    assert len(records) == DEFAULT_LIST_LIMIT
    assert last_sort_key == sorted_mock_records[-2].sk_artist_year

    # check order
    assert records[0].id == sorted_mock_records[0].id
    assert records[-1].id == sorted_mock_records[-2].id

    # check one record
    assert_list_item(sorted_mock_records[0], records[0])

    typed_mock_session.scalars.assert_called_once()
    scalars_mock.all.assert_called_once()

    arg_stmt = cast(Select, typed_mock_session.scalars.call_args[0][0])  # type: ignore
    # assert arg_stmt.whereclause is None

    stmt = (
        select(RecordModel)
        .limit(DEFAULT_LIST_LIMIT + 1)
        .where(RecordModel.sk_artist_year > cursor)
        .order_by(RecordModel.sk_artist_year)
        .options(selectinload(RecordModel.artists), selectinload(RecordModel.labels))
    )
    assert compile_statement(stmt) == compile_statement(arg_stmt)


def test_list_last_page():
    mock_records, _, _ = generate_records(DEFAULT_LIST_LIMIT)
    sorted_mock_records = sorted(mock_records, key=lambda r: r.sk_artist_year)

    mock_session = MagicMock()
    typed_mock_session = cast(MockedSession, mock_session)
    typed_mock_session.scalars = Mock()
    scalars_mock = typed_mock_session.scalars.return_value
    scalars_mock.all = Mock()
    scalars_mock.all.return_value = sorted_mock_records

    record_service = RecordService(mock_session)
    records, last_sort_key = record_service.list(
        limit=DEFAULT_LIST_LIMIT,
        last_cursor=None,
        sort_key_name=RecordSortOption.ARTIST_YEAR,
    )
    assert len(records) == DEFAULT_LIST_LIMIT
    assert last_sort_key is None

    # check order
    assert records[0].id == sorted_mock_records[0].id
    assert records[-1].id == sorted_mock_records[-1].id

    # check one record
    assert_list_item(sorted_mock_records[0], records[0])

    typed_mock_session.scalars.assert_called_once()
    scalars_mock.all.assert_called_once()

    arg_stmt = cast(Select, typed_mock_session.scalars.call_args[0][0])  # type: ignore
    assert arg_stmt.whereclause is None

    stmt = (
        select(RecordModel)
        .limit(DEFAULT_LIST_LIMIT + 1)
        .order_by(RecordModel.sk_artist_year)
        .options(selectinload(RecordModel.artists), selectinload(RecordModel.labels))
    )
    assert compile_statement(stmt) == compile_statement(arg_stmt)
