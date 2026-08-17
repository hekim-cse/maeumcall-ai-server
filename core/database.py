from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config import (
    DATABASE_CONNECT_TIMEOUT,
    DATABASE_MAX_OVERFLOW,
    DATABASE_POOL_SIZE,
    DATABASE_URL,
)


class DatabaseConfigurationError(RuntimeError):
    """Raised when the PostgreSQL connection contract is missing or invalid."""


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def validate_database_url(url: str) -> str:
    normalized = url.strip()
    if not normalized:
        raise DatabaseConfigurationError("DATABASE_URL is required")
    if not normalized.startswith("postgresql+asyncpg://"):
        raise DatabaseConfigurationError(
            "DATABASE_URL must use the postgresql+asyncpg driver"
        )
    return normalized


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            validate_database_url(DATABASE_URL),
            pool_pre_ping=True,
            pool_size=DATABASE_POOL_SIZE,
            max_overflow=DATABASE_MAX_OVERFLOW,
            connect_args={"timeout": DATABASE_CONNECT_TIMEOUT},
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def database_is_ready() -> bool:
    try:
        async with get_engine().connect() as connection:
            await connection.execute(text("SELECT 1"))
    except (
        DatabaseConfigurationError,
        SQLAlchemyError,
        OSError,
        RuntimeError,
        TimeoutError,
    ):
        return False
    return True


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
