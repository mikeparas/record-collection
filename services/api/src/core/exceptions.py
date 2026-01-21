from http import HTTPStatus
from typing import cast

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

VALIDATION_ERROR_CODE_MAP = {
    "string_type": "non_string",
    "string_too_short": "non_empty_string",
    "missing": "missing",
    "uuid_parsing": "non_uuid",
    "uuid_type": "non_uuid",
    "greater_than": "negative_number",
    "int_parsing": "non_integer",
    "empty_list": "empty_list",
    "too_short": "empty_list",
    "list_type": "non_list",
    "invalid_reference": "invalid_reference",
}

VALIDATION_ERROR_MSG_MAP = {
    "non_string": "Must be a string value.",
    "non_empty_string": "Must be a non-empty string value.",
    "missing": "Field is required.",
    "non_uuid": "Must be a valid UUID.",
    "negative_number": "Must be a positive value.",
    "non_integer": "Must be an integer value.",
    "empty_list": "Must be a non-empty list.",
    "non_list": "Must be a list value.",
}

VALIDATION_ERROR_DETAIL_MAP = {
    "postartists": ("Artist data", "ARTIST_VALIDATION_ERROR"),
    "postartists_v2": ("Artist data", "ARTIST_VALIDATION_ERROR"),
    "postlabels": ("Label data", "LABEL_VALIDATION_ERROR"),
    "getrecords": ("Record identifier", "RECORD_IDENTIFIER_ERROR"),
    "postrecords": ("Record data", "RECORD_VALIDATION_ERROR"),
}


class ErrorContent(BaseModel):
    type: str
    code: str
    message: str


class ValidationErrorDetail(BaseModel):
    field: str
    code: str
    message: str


class ValidationErrorContent(ErrorContent):
    details: list[ValidationErrorDetail]


class ErrorResponse(BaseModel):
    error: ValidationErrorContent | ErrorContent


class NotFoundException(Exception):
    status_code: int = HTTPStatus.NOT_FOUND
    code: str
    message: str

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message


class ConflictException(Exception):
    status_code: int = HTTPStatus.CONFLICT
    code: str
    message: str

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message


def not_found_exception_handler(request: Request, exc: Exception):
    typed_exc = cast(NotFoundException, exc)
    err_resp = ErrorResponse(
        error=ErrorContent(
            type="not_found", code=typed_exc.code, message=typed_exc.message
        )
    )
    return JSONResponse(
        status_code=typed_exc.status_code, content=jsonable_encoder(err_resp)
    )


def conflict_exception_handler(request: Request, exc: Exception):
    typed_exc = cast(ConflictException, exc)
    err_resp = ErrorResponse(
        error=ErrorContent(
            type="conflict", code=typed_exc.code, message=typed_exc.message
        )
    )
    return JSONResponse(
        status_code=typed_exc.status_code, content=jsonable_encoder(err_resp)
    )


def request_validation_error_handler(request: Request, exc: Exception):
    typed_exc = cast(RequestValidationError, exc)
    details: list[ValidationErrorDetail] = []

    path_parts = request.url.path.split("/")
    path_token = path_parts[1] if len(path_parts) > 1 else ""
    type_str, code = VALIDATION_ERROR_DETAIL_MAP.get(
        f"{request.method.lower()}{path_token}", ("Data", "VALIDATION_ERROR")
    )

    for error in typed_exc.errors():
        field_path = ".".join(str(loc) for loc in error["loc"][1:])
        error_code = VALIDATION_ERROR_CODE_MAP[error["type"]]

        detail_msg = (
            error["msg"]
            if error_code == "invalid_reference"
            else VALIDATION_ERROR_MSG_MAP[error_code]
        )

        details.append(
            ValidationErrorDetail(
                field=field_path,
                code=error_code,
                message=detail_msg,
            )
        )

    error_content = ValidationErrorContent(
        type="validation_error",
        code=code,
        message=f"{type_str} validation failed.",
        details=details,
    )

    error_resp = ErrorResponse(error=error_content)

    return JSONResponse(
        status_code=HTTPStatus.BAD_REQUEST, content=jsonable_encoder(error_resp)
    )
