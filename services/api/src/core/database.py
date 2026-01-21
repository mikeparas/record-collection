from sqlalchemy import URL, Engine, create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass, Session, sessionmaker

SessionLocal = sessionmaker(autocommit=False, autoflush=False, class_=Session)
AsyncSessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, class_=AsyncSession
)


class Base(MappedAsDataclass, DeclarativeBase):
    pass


class DatabaseConnector:
    sync_engine: Engine | None = None
    async_engine: AsyncEngine | None = None

    @classmethod
    def get_engine(
        cls, *, host: str, port: int, database: str, username: str, password: str
    ) -> Engine:
        if cls.sync_engine is not None:
            print("returning cached sync_engine...")
            return cls.sync_engine

        print(f"initializing new engine {(host, port, database, username)}")
        database_url = URL.create(
            "postgresql+psycopg",
            username=username,
            password=password,
            host=host,
            port=port,
            database=database,
        )

        cls.sync_engine = create_engine(database_url)
        SessionLocal.configure(bind=cls.sync_engine)
        print("returning new sync_engine...")
        return cls.sync_engine

    @classmethod
    def get_async_engine(
        cls, *, host: str, port: int, database: str, username: str, password: str
    ):
        if cls.async_engine is not None:
            return cls.async_engine

        database_url = URL.create(
            "postgresql+asyncpg",
            username=username,
            password=password,
            host=host,
            port=port,
            database=database,
        )

        cls.async_engine = create_async_engine(database_url)
        AsyncSessionLocal.configure(bind=cls.async_engine)
        return cls.async_engine

    @classmethod
    def reset_sync(cls):
        cls.sync_engine = None

    @classmethod
    def reset_async(cls):
        cls.async_engine = None

    @classmethod
    def reset(cls):
        cls.reset_sync()
        cls.reset_async()


def init_db(
    *, host: str, port: int, database: str, username: str, password: str
) -> Engine:
    engine = DatabaseConnector.get_engine(
        host=host, port=port, database=database, username=username, password=password
    )
    return engine


def init_async_db(
    *, host: str, port: int, database: str, username: str, password: str
) -> AsyncEngine:
    engine = DatabaseConnector.get_async_engine(
        host=host, port=port, database=database, username=username, password=password
    )
    return engine
