import uuid
from abc import abstractmethod
from collections.abc import Sequence
from typing import NoReturn, Protocol, TypeVar

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session


class ModelProtocol(Protocol):
    id: Mapped[uuid.UUID]
    name: Mapped[str]
    sort_name: Mapped[str]


T = TypeVar("T", bound=ModelProtocol)


class BaseService[T]:
    db: Session
    model: type[T]

    def __init__(self, db: Session, model: type[T]):
        self.db = db
        self.model = model

    def get_by(self, identifier: str) -> T | None:
        try:
            uuid_id = uuid.UUID(identifier)
            stmt = select(self.model).where(self.model.id == uuid_id)  # type: ignore
        except ValueError:
            stmt = select(self.model).where(self.model.name == identifier)  # type: ignore

        result = self.db.scalars(stmt)
        return result.one_or_none()

    def create_item(self, *, item: T) -> T:
        try:
            self.db.add(item)
            self.db.commit()
            return item
        except IntegrityError as exc:
            self.__class__.handle_integrity_error(exc, item=item)

    def list(
        self, *, limit: int, last_cursor: str | None = None
    ) -> tuple[Sequence[T], str | None]:
        stmt = select(self.model).order_by(self.model.sort_name).limit(limit + 1)  # type: ignore
        if last_cursor is not None:
            stmt = stmt.where(self.model.sort_name > last_cursor)  # type: ignore

        result = self.db.scalars(stmt)
        items = result.all()
        if len(items) == limit + 1:
            items = items[:limit]
            return items, items[-1].sort_name  # type: ignore

        return items, None

    @staticmethod
    @abstractmethod
    def handle_integrity_error(exc: IntegrityError, *, item: T) -> NoReturn: ...
