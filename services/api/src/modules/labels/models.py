from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import UniqueConstraint

from src.core.database import Base

if TYPE_CHECKING:
    from src.modules.records.models import RecordModel

CONSTRAINT_UNIQUE_NAME = "UQ_labels_name"
CONSTRAINT_UNIQUE_SORT_NAME = "UQ_labels_sort_name"


class LabelModel(Base):
    __tablename__ = "labels"
    __table_args__ = (
        UniqueConstraint("name", name=CONSTRAINT_UNIQUE_NAME),
        UniqueConstraint("sort_name", name=CONSTRAINT_UNIQUE_SORT_NAME),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=func.gen_random_uuid(), init=False
    )
    name: Mapped[str] = mapped_column(String)
    sort_name: Mapped[str] = mapped_column(String)

    records: Mapped[list[RecordModel]] = relationship(
        "RecordModel",
        secondary="records_labels",
        back_populates="labels",
        default_factory=list,
    )
