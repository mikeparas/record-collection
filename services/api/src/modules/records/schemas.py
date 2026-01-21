import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, StringConstraints

from src.modules.records.models import RecordData
from src.shared.schemas import BaseListResponse

type NonEmptyString = Annotated[
    str, StringConstraints(min_length=1, strip_whitespace=True)
]


class RecordArtist(BaseModel):
    id: uuid.UUID
    name: str

    model_config = ConfigDict(
        from_attributes=True, populate_by_name=True, extra="ignore"
    )


class RecordLabel(BaseModel):
    id: uuid.UUID
    name: str

    model_config = ConfigDict(
        from_attributes=True, populate_by_name=True, extra="ignore"
    )


class RecordItem(BaseModel):
    id: uuid.UUID
    title: str
    format_: str = Field(serialization_alias="format")
    yearRelease: int = Field(validation_alias="year_release")
    yearPressing: int = Field(validation_alias="year_pressing")
    data: RecordData
    artists: list[RecordArtist]
    labels: list[RecordLabel]
    sortArtistYear: str = Field(validation_alias="sk_artist_year")
    sortArtistTitle: str = Field(validation_alias="sk_artist_title")
    sortLabelArtistYear: str = Field(validation_alias="sk_label_artist_year")
    sortLabelYearArtist: str = Field(validation_alias="sk_label_year_artist")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class RecordDataCreate(BaseModel):
    color: NonEmptyString
    notes: NonEmptyString | None = Field(default=None)

    model_config = ConfigDict(
        from_attributes=True, populate_by_name=True, extra="ignore"
    )


class RecordCreate(BaseModel):
    title: NonEmptyString
    format_: Annotated[NonEmptyString, Field(validation_alias="format")]
    year_release: Annotated[PositiveInt, Field(validation_alias="yearRelease")]
    year_pressing: Annotated[PositiveInt, Field(validation_alias="yearPressing")]
    data: RecordDataCreate
    artists: list[uuid.UUID] = Field(min_length=1)
    labels: list[uuid.UUID]
    sk_artist_year: Annotated[NonEmptyString, Field(validation_alias="sortArtistYear")]
    sk_artist_title: Annotated[
        NonEmptyString, Field(validation_alias="sortArtistTitle")
    ]
    sk_label_artist_year: Annotated[
        NonEmptyString, Field(validation_alias="sortLabelArtistYear")
    ]
    sk_label_year_artist: Annotated[
        NonEmptyString, Field(validation_alias="sortLabelYearArtist")
    ]


class RecordListResponse(BaseListResponse[RecordItem]): ...
