import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from src.shared.schemas import BaseListResponse


class Artist(BaseModel):
    id: uuid.UUID
    name: str
    sort_name: str = Field(serialization_alias="sortName")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ArtistMessage(BaseModel):
    id_: Annotated[uuid.UUID, Field(validation_alias="id", serialization_alias="id")]
    name: str
    sort_name: Annotated[str, Field(serialization_alias="sortName")]
    discogs_id: Annotated[
        str | None, Field(default=None, serialization_alias="discogsId")
    ]

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ArtistCreate(BaseModel):
    name: Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]
    sort_name: Annotated[
        str,
        Field(validation_alias="sortName"),
        StringConstraints(min_length=1, strip_whitespace=True),
    ]
    discogs_id: Annotated[str | None, Field(default=None, validation_alias="discogsId")]

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ArtistListResponse(BaseListResponse[Artist]): ...
