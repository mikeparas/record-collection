from collections.abc import AsyncGenerator, Generator
from functools import lru_cache
from typing import Annotated

from aio_pika.abc import AbstractChannel
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from src.core.config import Settings
from src.core.database import AsyncSessionLocal, SessionLocal
from src.core.publisher import RabbitMQConnector
from src.modules.artists.publisher import ArtistPublisher
from src.modules.artists.service import ArtistAsyncService, ArtistService
from src.modules.health.service import HealthService
from src.modules.labels.service import LabelService
from src.modules.records.service import RecordService


@lru_cache
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]


def get_db() -> Generator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession]:
    async with AsyncSessionLocal() as db:
        yield db


async def get_publisher_channel():
    connection = RabbitMQConnector.get_connection()
    async with connection.channel() as channel:
        yield channel


async def get_artist_publisher(
    channel: Annotated[AbstractChannel, Depends(get_publisher_channel)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    return ArtistPublisher(channel=channel, exchange_name=settings.mq_exchange)


def get_artist_service(db: Annotated[Session, Depends(get_db)]):
    return ArtistService(db)


async def get_artist_async_service(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    publisher: Annotated[ArtistPublisher, Depends(get_artist_publisher)],
):
    return ArtistAsyncService(db, publisher)


def get_label_service(db: Annotated[Session, Depends(get_db)]):
    return LabelService(db)


def get_record_service(db: Annotated[Session, Depends(get_db)]):
    return RecordService(db)


def get_health_service(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    channel: Annotated[AbstractChannel, Depends(get_publisher_channel)],
) -> HealthService:
    """Get the health service."""
    return HealthService(db, channel)
