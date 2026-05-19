import base64
import json
from http import HTTPStatus
from typing import Annotated
from urllib.parse import urlencode, urljoin

import structlog
from fastapi import APIRouter, Depends, Path, Request, Response

from src.core.exceptions import NotFoundException
from src.dependencies import get_artist_async_service, get_artist_service
from src.modules.artists.schemas import (
    Artist,
    ArtistCreate,
    ArtistListResponse,
)
from src.modules.artists.service import (
    DEFAULT_LIST_LIMIT,
    ArtistAsyncService,
    ArtistService,
)
from src.shared.schemas import Pagination
from src.shared.types import Integrations

router = APIRouter(prefix="/artists", tags=["artists"])
router_v2 = APIRouter(prefix="/artists_v2")

log = structlog.stdlib.get_logger(module="artists.router")
# log = log.bind(module="artists.router")


@router.get(
    "/{identifier}",
    response_model=Artist,
    responses={
        404: {"description": "Artist Not Found"},
    },
)
def get_single_artist(
    identifier: Annotated[
        str,
        Path(title="Artist Identifier", description="UUID identifier or string name"),
    ],
    service: Annotated[ArtistService, Depends(get_artist_service)],
):
    """
    Get a single artist for a given UUID identifer or name
    """
    artist = service.get_by(identifier)

    if artist is None:
        raise NotFoundException(
            "ARTIST_NOT_FOUND", f"No artist found for {identifier}."
        )

    return artist


@router.post("/", response_model=Artist, status_code=HTTPStatus.CREATED)
def create_artist(
    artist_data: ArtistCreate,
    request: Request,
    response: Response,
    service: Annotated[ArtistService, Depends(get_artist_service)],
):
    artist = service.create(name=artist_data.name, sort_name=artist_data.sort_name)
    response.headers["Location"] = urljoin(
        str(request.base_url), f"{router.prefix}/{artist.name}"
    )
    return artist


@router_v2.post("", response_model=Artist, status_code=HTTPStatus.CREATED)
async def async_create_artist(
    artist_data: ArtistCreate,
    request: Request,
    response: Response,
    service: Annotated[ArtistAsyncService, Depends(get_artist_async_service)],
):
    # Extract correlation_id from request headers
    # (from API Gateway or fallback to None for auto-generation)
    correlation_id = request.headers.get("X-Correlation-ID")

    artist = await service.create(
        name=artist_data.name,
        sort_name=artist_data.sort_name,
        integrations=Integrations.model_validate(artist_data.integrations)
        if artist_data.integrations is not None
        else None,
        correlation_id=correlation_id,
    )
    response.headers["Location"] = urljoin(
        str(request.base_url), f"{router_v2.prefix}/{artist.name}"
    )
    return artist


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


@router.get("/", response_model=ArtistListResponse)
def list_artists(
    request: Request,
    service: Annotated[ArtistService, Depends(get_artist_service)],
    limit: int = DEFAULT_LIST_LIMIT,
    cursor: str | None = None,
):
    last_cursor = decode_token(cursor) if cursor is not None else None

    artists, last_sort_name = service.list(limit=limit, last_cursor=last_cursor)

    data_artists = [Artist.model_validate(artist) for artist in artists]

    next_cursor = None if last_sort_name is None else encode_cursor(last_sort_name)

    if next_cursor is not None:
        base_url = f"{request.base_url}{router.prefix.strip('/')}"
        qs_params = urlencode({"limit": limit, "cursor": next_cursor})
        next_link = f"{base_url}?{qs_params}"
    else:
        next_link = None

    return ArtistListResponse(
        data=data_artists,
        pagination=Pagination(
            limit=limit, next_cursor=next_cursor, next_link=next_link
        ),
    )


@router_v2.get(
    "/{identifier}",
    response_model=Artist,
    responses={
        404: {"description": "Artist Not Found"},
    },
)
async def async_get_single_artist(
    identifier: Annotated[
        str,
        Path(title="Artist Identifier", description="UUID identifier or string name"),
    ],
    service: Annotated[ArtistAsyncService, Depends(get_artist_async_service)],
):
    """
    Get a single artist for a given UUID identifer or name
    """
    log.info("Fetching single artist", identifier=identifier)

    artist = await service.get_by(identifier)

    if artist is None:
        log.info("Artist not found", identifier=identifier)
        raise NotFoundException(
            "ARTIST_NOT_FOUND", f"No artist found for {identifier}."
        )

    return artist
