import uuid
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_serializer,
)

from src.shared.schemas import BaseListResponse
from src.shared.types import ArtistExtraData, Integrations


class ArtistExtra(BaseModel):
    # ignore "id"
    data: ArtistExtraData | None = Field(default=None)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @model_serializer(mode="plain")
    def serialize_extra(self) -> ArtistExtraData | None:
        # return the data itself instead of {"data": ...}
        return self.data


class Artist(BaseModel):
    id: uuid.UUID
    name: str
    sort_name: str = Field(serialization_alias="sortName")
    integrations: Integrations | None = Field(default=None)
    extra: ArtistExtra | None = Field(default=None)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ArtistMessage(BaseModel):
    artist_id: Annotated[uuid.UUID, Field(serialization_alias="artistId")]

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ArtistCreate(BaseModel):
    name: Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]
    sort_name: Annotated[
        str,
        Field(validation_alias="sortName"),
        StringConstraints(min_length=1, strip_whitespace=True),
    ]
    integrations: Annotated[Integrations | None, Field(default=None)]

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ArtistListResponse(BaseListResponse[Artist]): ...
