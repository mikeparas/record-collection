from collections.abc import Sequence
from typing import TYPE_CHECKING, TypeVar, Union

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from src.modules.artists.schemas import Artist
    from src.modules.labels.schemas import Label
    from src.modules.records.schemas import RecordItem

T = TypeVar("T", bound=Union["Artist", "Label", "RecordItem"])


class Pagination(BaseModel):
    limit: int
    next_cursor: str | None = Field(default=None, serialization_alias="nextCursor")
    next_link: str | None = Field(default=None, serialization_alias="nextLink")


class BaseListResponse[T](BaseModel):
    data: Sequence[T]
    pagination: Pagination

    model_config = ConfigDict(from_attributes=True)
