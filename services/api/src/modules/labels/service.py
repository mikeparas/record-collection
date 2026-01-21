from typing import NoReturn

from psycopg import errors
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.exceptions import ConflictException
from src.modules.labels.models import (
    CONSTRAINT_UNIQUE_NAME,
    CONSTRAINT_UNIQUE_SORT_NAME,
    LabelModel,
)
from src.shared.service import BaseService

DEFAULT_LIST_LIMIT = 50


class LabelService(BaseService[LabelModel]):
    def __init__(self, db: Session):
        super().__init__(db, LabelModel)

    def create(self, *, name: str, sort_name: str) -> LabelModel:
        label = LabelModel(name=name, sort_name=sort_name)
        return super().create_item(item=label)

    @staticmethod
    def handle_integrity_error(exc: IntegrityError, *, item: LabelModel) -> NoReturn:
        if isinstance(
            exc.orig, errors.UniqueViolation
        ) and exc.orig.diag.constraint_name in [
            CONSTRAINT_UNIQUE_NAME,
            CONSTRAINT_UNIQUE_SORT_NAME,
        ]:
            attr_str = (
                f"sortName {item.sort_name}"
                if exc.orig.diag.constraint_name == CONSTRAINT_UNIQUE_SORT_NAME
                else f"name {item.name}"
            )
            raise ConflictException(
                code="LABEL_ALREADY_EXISTS",
                message=f"A label with {attr_str} already exists.",
            ) from exc
        raise exc
