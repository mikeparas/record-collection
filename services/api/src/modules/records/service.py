import uuid
from collections.abc import Sequence
from enum import StrEnum
from typing import Any, Protocol, TypedDict, TypeVar

from fastapi.exceptions import RequestValidationError
from sqlalchemy import select
from sqlalchemy.orm import Mapped, Session, selectinload

from src.modules.artists.models import ArtistModel
from src.modules.labels.models import LabelModel
from src.modules.records.models import RecordData, RecordModel


class ReferenceModelProtocol(Protocol):
    id: Mapped[uuid.UUID]
    name: Mapped[str]
    sort_name: Mapped[str]


class RecordValidationError(TypedDict):
    loc: list[str]
    type: str
    msg: str


T = TypeVar("T", bound=ReferenceModelProtocol)

DEFAULT_LIST_LIMIT = 25


def build_invalid_reference_error(
    loc: str, label: str, refs: list[str]
) -> RecordValidationError:
    return {
        "loc": ["body", loc],
        "type": "invalid_reference",
        "msg": f"{label} not found [{','.join(refs)}]",
    }


class RecordSortOption(StrEnum):
    ARTIST_YEAR = "artist_year"
    ARTIST_TITLE = "artist_title"
    LABEL_ARTIST = "label_artist_year"
    LABEL_YEAR = "label_year_artist"

    @classmethod
    def _missing_(cls, value: object) -> Any:
        return cls.ARTIST_YEAR


SORT_KEY_MAP = {
    RecordSortOption.ARTIST_YEAR: RecordModel.sk_artist_year,
    RecordSortOption.ARTIST_TITLE: RecordModel.sk_artist_title,
    RecordSortOption.LABEL_ARTIST: RecordModel.sk_label_artist_year,
    RecordSortOption.LABEL_YEAR: RecordModel.sk_label_year_artist,
}


class RecordService:
    db: Session

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by(self, identifier: uuid.UUID) -> RecordModel | None:
        stmt = (
            select(RecordModel)
            .where(RecordModel.id == identifier)
            .options(
                selectinload(RecordModel.artists), selectinload(RecordModel.labels)
            )
        )
        result = self.db.scalars(stmt)
        return result.one_or_none()

    def create(
        self,
        *,
        title: str,
        format_: str,
        year_release: int,
        year_pressing: int,
        data: RecordData,
        artist_ids: list[uuid.UUID],
        label_ids: list[uuid.UUID],
        sk_artist_year: str,
        sk_artist_title: str,
        sk_label_artist_year: str,
        sk_label_year_artist: str,
    ) -> RecordModel:
        errors: list[RecordValidationError] = []

        # get artists
        artists: list[ArtistModel] = []
        missing_artists: list[str] = []
        for artist_id in artist_ids:
            artist = self._find_model_by_id(ArtistModel, artist_id)
            if artist is None:
                missing_artists.append(str(artist_id))
            else:
                artists.append(artist)

        if len(missing_artists) > 0:
            errors.append(
                build_invalid_reference_error("artists", "Artists", missing_artists)
            )

        labels: list[LabelModel] = []
        missing_labels: list[str] = []
        for label_id in label_ids:
            label = self._find_model_by_id(LabelModel, label_id)
            if label is None:
                missing_labels.append(str(label_id))
            else:
                labels.append(label)

        if len(missing_labels) > 0:
            errors.append(
                build_invalid_reference_error("labels", "Labels", missing_labels)
            )

        if len(errors) > 0:
            raise RequestValidationError(errors)

        record_item = RecordModel(
            title=title,
            format_=format_,
            year_release=year_release,
            year_pressing=year_pressing,
            data=data,
            artists=artists,
            labels=labels,
            sk_artist_year=sk_artist_year,
            sk_artist_title=sk_artist_title,
            sk_label_artist_year=sk_label_artist_year,
            sk_label_year_artist=sk_label_year_artist,
        )

        self.db.add(record_item)
        self.db.commit()

        return record_item

    def list(
        self,
        *,
        limit: int,
        sort_key_name: RecordSortOption,
        last_cursor: str | None = None,
    ) -> tuple[Sequence[RecordModel], str | None]:
        use_sort_key = SORT_KEY_MAP.get(sort_key_name, RecordModel.sk_artist_year)
        stmt = (
            select(RecordModel)
            .limit(limit + 1)
            .order_by(use_sort_key)
            .options(
                selectinload(RecordModel.artists), selectinload(RecordModel.labels)
            )
        )
        if last_cursor is not None:
            stmt = stmt.where(use_sort_key > last_cursor)
        result = self.db.scalars(stmt)
        records = result.all()
        if len(records) == limit + 1:
            records = records[:limit]
            return records, getattr(records[-1], f"sk_{sort_key_name}")

        return records, None

    def _find_model_by_id[T](self, model: type[T], identifier: uuid.UUID) -> T | None:
        stmt = select(model).where(model.id == identifier)  # type: ignore
        result = self.db.scalars(stmt)
        return result.one_or_none()
