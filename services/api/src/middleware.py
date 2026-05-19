import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response


async def request_logging(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    log = structlog.stdlib.get_logger(module="middleware.request")

    request_id = uuid.uuid4()
    structlog.contextvars.bind_contextvars(
        path=request.url.path,
        method=request.method,
        request_id=request_id,
    )

    log.info("Request received")

    start_time = time.perf_counter()
    response = await call_next(request)
    end_time = time.perf_counter()

    log.info(
        "Request completed",
        duration=end_time - start_time,
        status_code=response.status_code,
    )

    return response
