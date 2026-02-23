from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import UniqueConstraint

from src.core.database import Base
from src.shared.types import Integrations, IntegrationsType

if TYPE_CHECKING:
    from src.modules.records.models import RecordModel

CONSTRAINT_UNIQUE_NAME = "UQ_artists_name"
CONSTRAINT_UNIQUE_SORT_NAME = "UQ_artists_sort_name"


class ArtistModel(Base):
    __tablename__ = "artists"
    __table_args__ = (
        UniqueConstraint("name", name=CONSTRAINT_UNIQUE_NAME),
        UniqueConstraint("sort_name", name=CONSTRAINT_UNIQUE_SORT_NAME),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=func.gen_random_uuid(), init=False
    )
    name: Mapped[str] = mapped_column(String)
    sort_name: Mapped[str] = mapped_column(String)
    integrations: Mapped[Integrations | None] = mapped_column(
        IntegrationsType(Integrations), default=None
    )

    records: Mapped[list[RecordModel]] = relationship(
        "RecordModel",
        secondary="records_artists",
        back_populates="artists",
        default_factory=list,
    )
