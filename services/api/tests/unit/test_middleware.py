import uuid
from http import HTTPStatus
from typing import Any

import pytest
import structlog
from fastapi import FastAPI, Request, Response
from structlog.testing import capture_logs

from src.middleware import request_logging

app = FastAPI()

mock_start_time = 1.0
mock_end_time = 2.5


@pytest.mark.asyncio
async def test_request_logging_middleware():
    # mock request ID generation
    mock_request_id = uuid.uuid4()

    # mock clock for request duration
    perf_counter_iter = iter([mock_start_time, mock_end_time])

    # mock call_next function for middleware
    async def mock_call_next(_: Request) -> Response:
        return Response(content="OK", status_code=HTTPStatus.OK)

    with capture_logs(processors=[structlog.contextvars.merge_contextvars]) as cap_logs:
        await request_logging(
            Request(
                scope={
                    "type": "http",
                    "method": "GET",
                    "headers": [],
                    "scheme": "http",
                    "server": ("127.0.0.1", 8000),
                    "path": "/test",
                }
            ),
            mock_call_next,
            clock=lambda: next(perf_counter_iter),
            generate_request_id=lambda: mock_request_id,
        )

        assert len(cap_logs) == 2

        # check each log has the injected context variables
        base_log: dict[str, Any] = {
            "module": "middleware.request",
            "path": "/test",
            "method": "GET",
            "request_id": mock_request_id,
        }
        for key, value in base_log.items():
            assert cap_logs[0].get(key) == value
            assert cap_logs[1].get(key) == value

        assert cap_logs[0].get("event") == "Request received"

        assert cap_logs[1].get("event") == "Request completed"
        assert cap_logs[1].get("status_code") == HTTPStatus.OK
        assert cap_logs[1].get("duration") == mock_end_time - mock_start_time
