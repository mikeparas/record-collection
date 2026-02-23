from typing import Any, TypeVar

from pydantic import BaseModel, Field
from sqlalchemy import TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB

T = TypeVar("T", bound=BaseModel)


class Integrations(BaseModel):
    discogs: int | None = Field(default=None)


class IntegrationsType(TypeDecorator[T]):
    impl = JSONB
    cache_ok = True

    def __init__(self, pydantic_model: type[T], **kwargs: Any):
        self.pydantic_model = pydantic_model
        super().__init__(**kwargs)

    def process_bind_param(
        self, value: T | dict[str, Any] | None, dialect: Any
    ) -> dict[str, Any] | None:
        if value is None:
            return None
        if isinstance(value, dict):
            return value
        return value.model_dump()

    def process_result_value(
        self, value: dict[str, Any] | None, dialect: Any
    ) -> T | None:
        if value is None:
            return None
        return self.pydantic_model.model_validate(value)
