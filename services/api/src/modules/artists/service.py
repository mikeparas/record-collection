import uuid
from typing import NoReturn

from asyncpg import exceptions
from psycopg import errors
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from src.core.exceptions import ConflictException
from src.modules.artists.models import (
    CONSTRAINT_UNIQUE_NAME,
    CONSTRAINT_UNIQUE_SORT_NAME,
    ArtistModel,
)
from src.modules.artists.publisher import ArtistPublisher
from src.modules.artists.schemas import ArtistMessage
from src.shared.service import BaseService
from src.shared.types import Integrations

DEFAULT_LIST_LIMIT = 50


def conflict_exception_detail(item: ArtistModel, constraint_name: str):
    return (
        f"sortName {item.sort_name}"
        if constraint_name == CONSTRAINT_UNIQUE_SORT_NAME
        else f"name {item.name}"
    )


def raise_conflict_exception(exc: IntegrityError, *, item: ArtistModel) -> NoReturn:
    if isinstance(
        exc.orig, errors.UniqueViolation
    ) and exc.orig.diag.constraint_name in [
        CONSTRAINT_UNIQUE_NAME,
        CONSTRAINT_UNIQUE_SORT_NAME,
    ]:
        attr_str = conflict_exception_detail(item, exc.orig.diag.constraint_name)
        raise ConflictException(
            code="ARTIST_ALREADY_EXISTS",
            message=f"An artist with {attr_str} already exists.",
        ) from exc
    raise


def raise_async_conflict_exception(
    exc: IntegrityError, *, item: ArtistModel
) -> NoReturn:
    cause = getattr(exc.orig, "__cause__", exc.orig)
    if isinstance(cause, exceptions.UniqueViolationError) and cause.constraint_name in [
        CONSTRAINT_UNIQUE_NAME,
        CONSTRAINT_UNIQUE_SORT_NAME,
    ]:
        attr_str = conflict_exception_detail(item, cause.constraint_name)
        raise ConflictException(
            code="ARTIST_ALREADY_EXISTS",
            message=f"An artist with {attr_str} already exists.",
        ) from exc
    raise


class ArtistService(BaseService[ArtistModel]):
    def __init__(self, db: Session):
        super().__init__(db, ArtistModel)

    def create(self, *, name: str, sort_name: str) -> ArtistModel:
        artist = ArtistModel(name=name, sort_name=sort_name)
        return super().create_item(item=artist)

    @staticmethod
    def handle_integrity_error(exc: IntegrityError, *, item: ArtistModel) -> NoReturn:
        raise_conflict_exception(exc, item=item)


class ArtistAsyncService:
    db: AsyncSession
    publisher: ArtistPublisher

    def __init__(self, db: AsyncSession, publisher: ArtistPublisher):
        self.db = db
        self.publisher = publisher

    async def get_by(self, identifier: str) -> ArtistModel | None:
        uuid_id = uuid.UUID(identifier)
        stmt = select(ArtistModel).where(ArtistModel.id == uuid_id)

        result = await self.db.scalars(stmt)
        return result.one_or_none()

    async def create(
        self,
        *,
        name: str,
        sort_name: str,
        integrations: Integrations | None = None,
        correlation_id: str | None = None,
    ) -> ArtistModel:
        artist = ArtistModel(name=name, sort_name=sort_name, integrations=integrations)
        try:
            self.db.add(artist)
            await self.db.commit()
            await self.db.refresh(artist)

            if artist.integrations is not None:
                message = ArtistMessage(artist_id=artist.id)
                await self.publisher.publish_message(
                    message, correlation_id=correlation_id
                )

            return artist
        except IntegrityError as exc:
            raise_async_conflict_exception(exc, item=artist)
