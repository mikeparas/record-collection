import base64
import json
from http import HTTPStatus
from typing import Annotated
from urllib.parse import urlencode, urljoin

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response

from src.dependencies import get_label_service
from src.modules.labels.schemas import Label, LabelCreate, LabelListResponse
from src.modules.labels.service import DEFAULT_LIST_LIMIT, LabelService
from src.shared.schemas import Pagination

router = APIRouter(prefix="/labels", tags=["labels"])


@router.get(
    "/{identifier}",
    response_model=Label,
    responses={404: {"description": "Label Not Found"}},
)
def get_single_label(
    identifier: Annotated[
        str,
        Path(title="Label Identifier", description="UUID identifier or string name"),
    ],
    service: Annotated[LabelService, Depends(get_label_service)],
):
    """
    Get a single label for a given UUID identifier or name
    """
    label = service.get_by(identifier)
    if label is None:
        raise HTTPException(
            HTTPStatus.NOT_FOUND, detail=f"No label found for {identifier}."
        )

    return label


@router.post("/", response_model=Label, status_code=HTTPStatus.CREATED)
def create_label(
    label_data: LabelCreate,
    request: Request,
    response: Response,
    service: Annotated[LabelService, Depends(get_label_service)],
):
    label = service.create(name=label_data.name, sort_name=label_data.sort_name)
    response.headers["Location"] = urljoin(
        str(request.base_url), f"{router.prefix}/{label.name}"
    )
    return label


def encode_cursor(sort_name: str) -> str:
    payload = {"sort_name": sort_name}

    json_bytes = json.dumps(payload).encode("utf8")

    encoded_bytes = base64.urlsafe_b64encode(json_bytes).rstrip(b"=")

    return encoded_bytes.decode("utf8")


def decode_token(token: str) -> str:
    token_bytes = token.encode("utf8")
    json_bytes = base64.urlsafe_b64decode(token_bytes + b"===")
    payload = json.loads(json_bytes.decode("utf8"))

    return payload.get("sort_name")


@router.get("/", response_model=LabelListResponse)
def list_labels(
    request: Request,
    service: Annotated[LabelService, Depends(get_label_service)],
    limit: int = DEFAULT_LIST_LIMIT,
    cursor: str | None = None,
):
    last_cursor = decode_token(cursor) if cursor is not None else None

    labels, last_sort_name = service.list(limit=limit, last_cursor=last_cursor)

    data_labels = [Label.model_validate(label) for label in labels[:limit]]

    next_cursor = encode_cursor(last_sort_name) if last_sort_name is not None else None

    if next_cursor is not None:
        base_url = f"{request.base_url}{router.prefix.strip('/')}"
        qs_params = urlencode({"limit": limit, "cursor": next_cursor})
        next_link = f"{base_url}?{qs_params}"
    else:
        next_link = None

    return LabelListResponse(
        data=data_labels,
        pagination=Pagination(
            limit=limit, next_cursor=next_cursor, next_link=next_link
        ),
    )
