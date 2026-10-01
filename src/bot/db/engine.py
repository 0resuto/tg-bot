"""Database engine and session factory setup."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_async_engine_instance(dsn: str) -> AsyncEngine:
    """Create and return an async SQLAlchemy engine with pre-ping and pool recycling."""
    return create_async_engine(
        dsn,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create and return a session factory for the given engine."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
