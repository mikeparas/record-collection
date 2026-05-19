from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError

from src.core.config import settings
from src.core.database import init_async_db, init_db
from src.core.exceptions import (
    ConflictException,
    NotFoundException,
    conflict_exception_handler,
    not_found_exception_handler,
    request_validation_error_handler,
)
from src.core.logging import init_logger
from src.core.publisher import RabbitMQConnector, setup_channel
from src.middleware import request_logging
from src.modules.artists.router import router as artist_router
from src.modules.artists.router import router_v2 as async_artist_router
from src.modules.health.router import router as health_router
from src.modules.labels.router import router as label_router
from src.modules.records.router import router as record_router

init_logger()

log = structlog.stdlib.get_logger(module="main")


@asynccontextmanager
async def lifespan(_: FastAPI):
    log.info("Initializing application")

    init_db(
        host=settings.db_host,
        port=int(settings.db_port),
        database=settings.db_name,
        username=settings.db_app_user,
        password=settings.db_app_pass,
    )

    init_async_db(
        host=settings.db_host,
        port=int(settings.db_port),
        database=settings.db_name,
        username=settings.db_app_user,
        password=settings.db_app_pass,
    )

    connection = await RabbitMQConnector.connect(
        host=settings.mq_host,
        port=int(settings.mq_port),
        username=settings.mq_user,
        password=settings.mq_pass,
    )

    async with connection.channel() as channel:
        await setup_channel(
            channel, settings.mq_exchange, settings.mq_queue_external_data
        )

    yield

    log.info("Closing application")

    await RabbitMQConnector.close()


app = FastAPI(
    lifespan=lifespan,
    exception_handlers={
        NotFoundException: not_found_exception_handler,
        RequestValidationError: request_validation_error_handler,
        ConflictException: conflict_exception_handler,
    },  # type: ignore
)
app.include_router(health_router)
app.include_router(artist_router)
app.include_router(async_artist_router)
app.include_router(label_router)
app.include_router(record_router)


@app.middleware("http")
async def request_logging_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
):
    return await request_logging(request, call_next)
