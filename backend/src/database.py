"""Database configuration and session management."""

from collections.abc import AsyncGenerator, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from src.config import Settings, get_settings


class Base(DeclarativeBase):
    """Base class for all database models."""


# Module-level singletons (application-scoped)
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _make_async_url(url: str) -> str:
    """Convert a database URL to its async-compatible dialect."""
    if url.startswith("sqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    # Already async-compatible or custom dialect
    return url


def initialize_database(settings: Settings) -> None:
    """Initialize database engine and session factory once at startup.

    Subsequent calls are no-ops so the embedded worker does not create a
    duplicate connection pool when the FastAPI lifespan already initialised it.
    """
    global _engine, _session_factory  # noqa: PLW0603

    if _engine is not None:
        return

    async_url = _make_async_url(settings.DATABASE_URL)

    # Connection pool configuration
    if async_url.startswith("sqlite"):
        _engine = create_async_engine(
            async_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        _engine = create_async_engine(
            async_url,
            pool_size=20,  # Base pool size
            max_overflow=30,  # Allow 10 extra connections under load
            pool_pre_ping=True,  # Verify connections before use
            pool_recycle=3600,  # Recycle connections after 1 hour
        )

    _session_factory = async_sessionmaker(
        autocommit=False, autoflush=False, expire_on_commit=False, bind=_engine
    )


def get_session_factory(
    settings: Annotated[Settings, Depends(get_settings)],
) -> async_sessionmaker[AsyncSession]:
    """Get session factory (returns singleton)."""
    if _session_factory is None:
        # Fallback for backwards compatibility
        initialize_database(settings)

    if _session_factory is None:
        raise RuntimeError("Failed to initialize database session factory.")

    return _session_factory


async def dispose_engine() -> None:
    """Dispose database engine on shutdown."""
    global _engine, _session_factory  # noqa: PLW0603
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


async def get_db(
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    async with session_factory() as db:
        yield db


# The session the DI container should build repositories against. A ContextVar
# rather than a module global: every request runs in its own asyncio task, which
# carries its own copy of the context, so concurrent requests cannot see each
# other's binding. Sync dependencies dispatched to the threadpool inherit a copy
# of the caller's context, so they are covered too.
_request_db_session: ContextVar[AsyncSession] = ContextVar("request_db_session")


@contextmanager
def bind_db_session(session: AsyncSession) -> Iterator[None]:
    """Bind a database session for the duration of the block."""
    token = _request_db_session.set(session)
    try:
        yield
    finally:
        _request_db_session.reset(token)


def current_db_session() -> AsyncSession:
    """Get the session bound to the current context.

    Raises:
        RuntimeError: If no session is bound, which means a provider was
            resolved outside of a ``bind_db_session`` block.
    """
    try:
        return _request_db_session.get()
    except LookupError as exc:
        msg = (
            "No database session is bound to the current context. "
            "Resolve container providers inside a bind_db_session(...) block."
        )
        raise RuntimeError(msg) from exc


# Type alias for database dependency
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
