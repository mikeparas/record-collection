from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel
from sqlalchemy import Column, ForeignKey, Integer, String, Table, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base

if TYPE_CHECKING:
    from src.modules.artists.models import ArtistModel
    from src.modules.labels.models import LabelModel

from sqlalchemy.types import TypeDecorator

# Association tables for many-to-many relationships
records_artists = Table(
    "records_artists",
    Base.metadata,
    Column("record_id", UUID(as_uuid=True), ForeignKey("records.id"), primary_key=True),
    Column("artist_id", UUID(as_uuid=True), ForeignKey("artists.id"), primary_key=True),
)

records_labels = Table(
    "records_labels",
    Base.metadata,
    Column("record_id", UUID(as_uuid=True), ForeignKey("records.id"), primary_key=True),
    Column("label_id", UUID(as_uuid=True), ForeignKey("labels.id"), primary_key=True),
)

T = TypeVar("T", bound=BaseModel)


class RecordData(BaseModel):
    color: str
    notes: str | None = None


class RecordDataType(TypeDecorator[T]):
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


class RecordModel(Base):
    __tablename__ = "records"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=func.gen_random_uuid(), init=False
    )
    title: Mapped[str] = mapped_column(String, nullable=False, index=True)
    format_: Mapped[str] = mapped_column(String, nullable=False, name="format")
    year_release: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    year_pressing: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sk_artist_year: Mapped[str] = mapped_column(String, nullable=False, index=True)
    sk_artist_title: Mapped[str] = mapped_column(String, nullable=False, index=True)
    sk_label_year_artist: Mapped[str] = mapped_column(
        String, nullable=False, index=True
    )
    sk_label_artist_year: Mapped[str] = mapped_column(
        String, nullable=False, index=True
    )
    data: Mapped[RecordData] = mapped_column(RecordDataType(RecordData), nullable=False)

    # Many-to-many relationships
    artists: Mapped[list[ArtistModel]] = relationship(
        "ArtistModel",
        secondary=records_artists,
        back_populates="records",
    )
    labels: Mapped[list[LabelModel]] = relationship(
        "LabelModel",
        secondary=records_labels,
        back_populates="records",
    )
