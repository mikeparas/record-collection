import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from src.shared.schemas import BaseListResponse


class Label(BaseModel):
    id: uuid.UUID
    name: str
    sortName: str = Field(validation_alias="sort_name")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class LabelCreate(BaseModel):
    name: Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]
    sort_name: Annotated[
        str,
        Field(validation_alias="sortName"),
        StringConstraints(min_length=1, strip_whitespace=True),
    ]

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class LabelListResponse(BaseListResponse[Label]): ...
