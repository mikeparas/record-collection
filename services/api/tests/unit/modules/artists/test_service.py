import uuid
from collections.abc import Callable, Sequence
from typing import (
    Any,
    cast,
)
from unittest.mock import AsyncMock, Mock

import pytest
from asyncpg import exceptions
from psycopg import errors
from sqlalchemy import Select, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from src.core.exceptions import ConflictException
from src.modules.artists.models import ArtistModel, Integrations
from src.modules.artists.publisher import ArtistPublisher
from src.modules.artists.schemas import ArtistMessage
from src.modules.artists.service import (
    DEFAULT_LIST_LIMIT,
    ArtistAsyncService,
    ArtistService,
)
from tests.utils import generate_artists


def compile_statement(stmt: Select[Any]) -> str:
    return str(
        stmt.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )


@pytest.fixture
def mock_publisher() -> ArtistPublisher | AsyncMock:
    publisher = AsyncMock()
    publisher.publish_message = AsyncMock()
    return publisher


def get_mock_session(
    *,
    scalars_one_or_none_return: ArtistModel | None = None,
    add_side_effect: Callable[[ArtistModel], None] | None = None,
    commit_side_effect: Exception | None = None,
    scalars_all_return_value: Sequence[ArtistModel] = [],
) -> Session:
    session = Mock()

    session.scalars = Mock()
    mock_scalars = session.scalars.return_value
    mock_scalars.one_or_none.return_value = scalars_one_or_none_return
    mock_scalars.all.return_value = scalars_all_return_value

    session.add = Mock()
    if add_side_effect is not None:
        session.add.side_effect = add_side_effect

    session.commit = Mock()
    if commit_side_effect is not None:
        session.commit.side_effect = commit_side_effect

    return session


def get_mock_async_session(
    add_side_effect: Callable[[ArtistModel], None] | None = None,
    commit_side_effect: Exception | None = None,
) -> AsyncSession:
    session = AsyncMock()
    session.add = Mock()
    if add_side_effect is not None:
        session.add.side_effect = add_side_effect
    session.commit = AsyncMock()
    if commit_side_effect is not None:
        session.commit.side_effect = commit_side_effect
    session.refresh = AsyncMock()

    return session


def assert_select(identifier: str, mock_session: Mock):
    try:
        uuid_id = uuid.UUID(identifier)
        stmt = select(ArtistModel).where(ArtistModel.id == uuid_id)
    except ValueError:
        stmt = select(ArtistModel).where(ArtistModel.name == identifier)

    arg_stmt = cast(Mock, mock_session.scalars).call_args[0][0]
    assert compile_statement(stmt) == compile_statement(arg_stmt)

    cast(Mock, mock_session.scalars.return_value.one_or_none).assert_called_once()


def assert_create(name: str, sort_name: str, mock_session: Mock):
    add_arg = cast(Mock, mock_session.add).call_args[0][0]
    assert isinstance(add_arg, ArtistModel)
    assert add_arg.name == name
    assert add_arg.sort_name == sort_name

    cast(Mock, mock_session.commit).assert_called_once()


def assert_list(mock_session: Mock, cursor: str | None = None):
    stmt = (
        select(ArtistModel)
        .order_by(ArtistModel.sort_name)
        .limit(DEFAULT_LIST_LIMIT + 1)
    )
    if cursor is not None:
        stmt = stmt.where(ArtistModel.sort_name > cursor)
    arg_stmt = cast(Mock, mock_session.scalars).call_args[0][0]
    assert compile_statement(stmt) == compile_statement(arg_stmt)

    cast(Mock, mock_session.scalars.return_value.all).assert_called_once()


def test_get_by_id():
    mock_id = uuid.uuid4()
    mock_artist = ArtistModel(name="Test Artist", sort_name="testartist")
    mock_artist.id = mock_id

    mock_session = get_mock_session(scalars_one_or_none_return=mock_artist)

    artist_service = ArtistService(mock_session)
    artist = artist_service.get_by(str(mock_id))
    assert artist is not None
    assert artist.id == mock_id
    assert artist.name == mock_artist.name
    assert artist.sort_name == mock_artist.sort_name

    assert_select(str(mock_id), cast(Mock, mock_session))


def test_get_by_name():
    mock_id = uuid.uuid4()
    mock_artist = ArtistModel(name="Test Artist", sort_name="testartist")
    mock_artist.id = mock_id

    mock_session = get_mock_session(scalars_one_or_none_return=mock_artist)

    artist_service = ArtistService(mock_session)
    artist = artist_service.get_by(mock_artist.name)
    assert artist is not None
    assert artist.id == mock_id
    assert artist.name == mock_artist.name
    assert artist.sort_name == mock_artist.sort_name

    assert_select(mock_artist.name, cast(Mock, mock_session))


def test_get_by_not_found():
    mock_session = get_mock_session(scalars_one_or_none_return=None)

    name = "Not Found"

    artist_service = ArtistService(mock_session)
    artist = artist_service.get_by(name)
    assert artist is None

    assert_select(name, cast(Mock, mock_session))


def test_create():
    mock_id = uuid.uuid4()

    def mock_add(instance: ArtistModel):
        instance.id = mock_id

    mock_session = get_mock_session(add_side_effect=mock_add)

    name = "New Artist"
    sort_name = "newartist"

    artist_service = ArtistService(mock_session)
    artist = artist_service.create(name=name, sort_name=sort_name)
    assert artist.id == mock_id
    assert artist.name == name
    assert artist.sort_name == sort_name

    assert_create(name, sort_name, cast(Mock, mock_session))


@pytest.mark.asyncio
@pytest.mark.parametrize("discogs_id, should_publish", [(None, False), (123456, True)])
async def test_async_create_integrations(
    discogs_id: int | None,
    should_publish: bool,
    mock_publisher: ArtistPublisher | AsyncMock,
):
    mock_id = uuid.uuid4()

    def mock_add(instance: ArtistModel):
        instance.id = mock_id

    mock_session = get_mock_async_session(mock_add)

    name = "New Artist"
    sort_name = "newartist"

    integrations = Integrations(discogs=discogs_id) if discogs_id is not None else None

    artist_service = ArtistAsyncService(mock_session, mock_publisher)
    artist = await artist_service.create(
        name=name, sort_name=sort_name, integrations=integrations
    )
    assert artist.id == mock_id
    assert artist.name == name
    assert artist.sort_name == sort_name
    assert artist.integrations == integrations

    add_arg = cast(Mock, mock_session.add).call_args[0][0]
    assert isinstance(add_arg, ArtistModel)
    assert add_arg.name == name
    assert add_arg.sort_name == sort_name

    cast(AsyncMock, mock_session.commit).assert_called_once()
    cast(AsyncMock, mock_session.refresh).assert_called_once()

    mock_publish = cast(AsyncMock, mock_publisher.publish_message)
    if should_publish:
        artist_message = ArtistMessage(artist_id=artist.id)
        mock_publish.assert_called_once()
        args, _ = mock_publish.call_args
        expected_message: ArtistMessage = args[0]
        assert expected_message.artist_id == artist_message.artist_id
        # assert expected_message.name == artist_message.name
        # assert expected_message.sort_name == artist_message.sort_name
        # assert expected_message.discogs_id == artist_message.discogs_id
    else:
        mock_publish.assert_not_called()


@pytest.mark.parametrize(
    "constraint,error_msg",
    [
        # adjust error messages with artist data in the test
        ("UQ_artists_name", "An artist with name Duplicate Artist already exists."),
        (
            "UQ_artists_sort_name",
            "An artist with sortName duplicateartist already exists.",
        ),
    ],
)
def test_create_duplicate(constraint: str, error_msg: str):
    # mock psycopg error
    orig_error = Mock(spec=errors.UniqueViolation)
    orig_error.diag = Mock()  # type: ignore
    orig_error.diag.constraint_name = constraint
    orig_error.diag.table_name = "artists"
    orig_error.diag.schema_name = "public"

    # mock IntegrityError
    integrity_error = IntegrityError(
        statement="insert statement", params={}, orig=orig_error
    )

    mock_session = get_mock_session(commit_side_effect=integrity_error)

    name = "Duplicate Artist"
    sort_name = "duplicateartist"

    artist_service = ArtistService(mock_session)
    with pytest.raises(ConflictException) as exc:
        artist_service.create(name=name, sort_name=sort_name)

    assert exc.value.code == "ARTIST_ALREADY_EXISTS"
    assert exc.value.message == error_msg

    assert_create(name, sort_name, cast(Mock, mock_session))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "constraint,error_msg",
    [
        # adjust error messages with artist data in the test
        ("UQ_artists_name", "An artist with name Duplicate Artist already exists."),
        (
            "UQ_artists_sort_name",
            "An artist with sortName duplicateartist already exists.",
        ),
    ],
)
async def test_async_create_duplicate(
    constraint: str, error_msg: str, mock_publisher: AsyncMock | ArtistPublisher
):
    # mock asyngpc error
    orig_error = Mock()
    orig_error.__cause__ = Mock(spec=exceptions.UniqueViolationError)  # type: ignore
    orig_error.__cause__.constraint_name = constraint
    orig_error.__cause__.table_name = "artists"
    orig_error.__cause__.schema_name = "public"

    # mock IntegrityError
    integrity_error = IntegrityError(
        statement="insert statement", params={}, orig=orig_error
    )

    mock_session = get_mock_async_session(None, integrity_error)

    name = "Duplicate Artist"
    sort_name = "duplicateartist"

    artist_service = ArtistAsyncService(mock_session, mock_publisher)
    with pytest.raises(ConflictException) as exc:
        await artist_service.create(name=name, sort_name=sort_name)

    assert exc.value.code == "ARTIST_ALREADY_EXISTS"
    assert exc.value.message == error_msg

    cast(Mock, mock_session.add).assert_called_once_with(
        ArtistModel(name=name, sort_name=sort_name)
    )
    cast(AsyncMock, mock_session.commit).assert_called_once()

    cast(AsyncMock, mock_publisher.publish_message).assert_not_called()


def test_list():
    mock_artists = generate_artists(DEFAULT_LIST_LIMIT + 1)

    mock_session = get_mock_session(scalars_all_return_value=mock_artists)

    artist_service = ArtistService(mock_session)
    artists, last_sort_name = artist_service.list(
        limit=DEFAULT_LIST_LIMIT, last_cursor=None
    )
    assert len(artists) == DEFAULT_LIST_LIMIT
    assert last_sort_name == mock_artists[-2].sort_name

    assert_list(cast(Mock, mock_session))


def test_list_empty():
    mock_session = get_mock_session(scalars_all_return_value=[])

    artist_service = ArtistService(mock_session)
    artists, last_sort_name = artist_service.list(
        limit=DEFAULT_LIST_LIMIT, last_cursor=None
    )
    assert len(artists) == 0
    assert last_sort_name is None

    assert_list(cast(Mock, mock_session))


def test_list_last_cursor():
    mock_artists = generate_artists(DEFAULT_LIST_LIMIT + 1)

    mock_session = get_mock_session(scalars_all_return_value=mock_artists)

    cursor = "lastsortname"

    artist_service = ArtistService(mock_session)
    artists, last_sort_name = artist_service.list(
        limit=DEFAULT_LIST_LIMIT, last_cursor=cursor
    )
    assert len(artists) == DEFAULT_LIST_LIMIT
    assert last_sort_name == mock_artists[-2].sort_name

    assert_list(cast(Mock, mock_session), cursor)


def test_list_last_page():
    mock_artists = generate_artists(50)

    mock_session = get_mock_session(scalars_all_return_value=mock_artists)

    artist_service = ArtistService(mock_session)
    artists, last_sort_name = artist_service.list(
        limit=DEFAULT_LIST_LIMIT, last_cursor=None
    )
    assert len(artists) == DEFAULT_LIST_LIMIT
    assert last_sort_name is None

    assert_list(cast(Mock, mock_session))
