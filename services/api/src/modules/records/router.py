import base64
import json
import uuid
from http import HTTPStatus
from typing import Annotated
from urllib.parse import urlencode, urljoin

from fastapi import APIRouter, Depends, Request, Response

from src.core.exceptions import NotFoundException
from src.dependencies import get_record_service
from src.modules.records.models import RecordData
from src.modules.records.schemas import (
    RecordCreate,
    RecordItem,
    RecordListResponse,
)
from src.modules.records.service import (
    DEFAULT_LIST_LIMIT,
    RecordService,
    RecordSortOption,
)
from src.shared.schemas import Pagination

router = APIRouter(prefix="/records", tags=["records"])


@router.get("/{identifier}", response_model=RecordItem)
def get_single_record(
    identifier: uuid.UUID,
    service: Annotated[RecordService, Depends(get_record_service)],
):
    record_item = service.get_by(identifier)
    if record_item is None:
        raise NotFoundException(
            "RECORD_NOT_FOUND", f"No record found for {identifier}."
        )

    return record_item


@router.post("/", response_model=RecordItem, status_code=HTTPStatus.CREATED)
def create_record(
    record_data: RecordCreate,
    request: Request,
    response: Response,
    service: Annotated[RecordService, Depends(get_record_service)],
):
    record_item = service.create(
        title=record_data.title,
        format_=record_data.format_,
        year_release=record_data.year_release,
        year_pressing=record_data.year_pressing,
        data=RecordData(color=record_data.data.color, notes=record_data.data.notes),
        artist_ids=record_data.artists,
        label_ids=record_data.labels,
        sk_artist_year=record_data.sk_artist_year,
        sk_artist_title=record_data.sk_artist_title,
        sk_label_artist_year=record_data.sk_label_artist_year,
        sk_label_year_artist=record_data.sk_label_year_artist,
    )

    response.headers["Location"] = urljoin(
        str(request.base_url), f"{router.prefix}/{str(record_item.id)}"
    )
    return record_item


def encode_cursor(sort_name: str) -> str:
    payload = {"sort_key": sort_name}

    json_bytes = json.dumps(payload).encode("utf8")

    encoded_bytes = base64.urlsafe_b64encode(json_bytes).rstrip(b"=")

    return encoded_bytes.decode("utf8")


def decode_token(token: str) -> str:
    token_bytes = token.encode("utf8")
    json_bytes = base64.urlsafe_b64decode(token_bytes + b"===")
    payload = json.loads(json_bytes.decode("utf8"))

    return payload.get("sort_key")


@router.get("/", response_model=RecordListResponse)
def list_records(
    request: Request,
    service: Annotated[RecordService, Depends(get_record_service)],
    limit: int = DEFAULT_LIST_LIMIT,
    cursor: str | None = None,
    sort: RecordSortOption = RecordSortOption.ARTIST_YEAR,
):
    sort_key_name = (
        RecordSortOption(sort)
        if sort in RecordSortOption
        else RecordSortOption.ARTIST_YEAR
    )

    last_cursor = decode_token(cursor) if cursor is not None else None

    sorted_records, last_sort_key = service.list(
        limit=limit,
        sort_key_name=sort_key_name,
        last_cursor=last_cursor,
    )

    data_records = [
        RecordItem.model_validate(record_item) for record_item in sorted_records
    ]

    if last_sort_key is not None:
        next_cursor = encode_cursor(last_sort_key)
        base_url = f"{request.base_url}{router.prefix.strip('/')}"
        qs_params = urlencode({"limit": limit, "cursor": next_cursor, "sort": sort})
        next_link = f"{base_url}?{qs_params}"
    else:
        next_cursor = None
        next_link = None

    return RecordListResponse(
        data=data_records,
        pagination=Pagination(
            limit=limit, next_cursor=next_cursor, next_link=next_link
        ),
    )
