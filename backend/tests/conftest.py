"""Pytest configuration and fixtures."""

import itertools
import logging
import os

# Settings are constructed at import time in src.main, so env vars that feed
# the Settings validator must be set before any src.* imports below.
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-bytes-long")
os.environ.setdefault(
    "REFRESH_TOKEN_SECRET_KEY",
    "test-refresh-token-secret-key-at-least-32-bytes-long",
)
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import datetime as dt
from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from src.database import Base, get_db
from src.domain.common.value_objects import ContentHash
from src.domain.common.value_objects.ids import UserId
from src.domain.identity.entities.user import User as DomainUser
from src.infrastructure.identity.dependencies import get_current_user
from src.infrastructure.library.schemas import EreaderBookMetadata
from src.main import app
from src.models import (
    Book,
    Chapter,
    Flashcard,
    Highlight,
    Tag,
    TagGroup,
    User,
)
from src.models import (
    HighlightStyle as HighlightStyleModel,
)

logging.getLogger("aiosqlite").setLevel(logging.WARNING)


async def create_test_book(
    db_session: AsyncSession,
    user_id: int,
    title: str,
    author: str | None = None,
    isbn: str | None = None,
    description: str | None = None,
    language: str | None = None,
    page_count: int | None = None,
    client_book_id: str | None = None,
) -> Book:
    """Create a test book with properly computed content_hash.

    This helper ensures all test books have valid content_hash values.
    """
    book = Book(
        user_id=user_id,
        title=title,
        author=author,
        isbn=isbn,
        description=description,
        language=language,
        page_count=page_count,
        client_book_id=client_book_id,
    )
    db_session.add(book)
    await db_session.commit()
    await db_session.refresh(book)
    return book


async def create_test_chapter(
    db_session: AsyncSession,
    book: Book,
    name: str,
    chapter_number: int | None = None,
    parent_id: int | None = None,
) -> Chapter:
    """Attach a chapter to a book."""
    chapter = Chapter(
        book_id=book.id, name=name, chapter_number=chapter_number, parent_id=parent_id
    )
    db_session.add(chapter)
    await db_session.commit()
    await db_session.refresh(chapter)
    return chapter


async def create_test_highlight(
    db_session: AsyncSession,
    book: Book,
    user_id: int,
    text: str,
    datetime_str: str,
    page: int | None = None,
    chapter_id: int | None = None,
    deleted_at: dt | None = None,
    start_xpoint: str | None = None,
    end_xpoint: str | None = None,
    highlight_style_id: int | None = None,
) -> Highlight:
    """Create a test highlight with properly computed content_hash.

    This helper ensures all test highlights have valid content_hash values.
    Hash is computed from text only, matching domain entity behavior.
    """
    # Compute hash from text only (deduplication happens within book context)
    content_hash = ContentHash.compute(text).value

    highlight = Highlight(
        book_id=book.id,
        user_id=user_id,
        chapter_id=chapter_id,
        text=text,
        page=page,
        start_xpoint=start_xpoint,
        end_xpoint=end_xpoint,
        datetime=datetime_str,
        content_hash=content_hash,
        deleted_at=deleted_at,
        highlight_style_id=highlight_style_id,
    )
    db_session.add(highlight)
    await db_session.commit()
    await db_session.refresh(highlight)
    return highlight


async def create_test_highlight_style(
    db_session: AsyncSession,
    user_id: int,
    book_id: int,
    device_color: str = "gray",
    device_style: str = "lighten",
    label: str | None = None,
    ui_color: str | None = None,
) -> HighlightStyleModel:
    """Create a test highlight style."""
    style = HighlightStyleModel(
        user_id=user_id,
        book_id=book_id,
        device_color=device_color,
        device_style=device_style,
        label=label,
        ui_color=ui_color,
    )
    db_session.add(style)
    await db_session.commit()
    await db_session.refresh(style)
    return style


# Test database URL (in-memory SQLite with aiosqlite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create test engine with StaticPool to reuse the same connection
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


# Enable SQLite foreign key enforcement for cascade deletes
@event.listens_for(test_engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection: object, connection_record: object) -> None:  # pyright: ignore[reportUnusedFunction]
    cursor = dbapi_connection.cursor()  # type: ignore[union-attr]
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# Create test session factory
TestSessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False
)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    # Create all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        # Create the default user that services expect
        default_user = User(id=1, email="admin@test.com")
        session.add(default_user)
        await session.commit()
        yield session

    # Drop all tables after test
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Get the default test user."""
    result = await db_session.execute(select(User).filter_by(id=1))
    user = result.scalar_one_or_none()
    assert user is not None
    return user


@pytest.fixture
async def client(db_session: AsyncSession, test_user: User) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with database session and mocked authentication."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_get_current_user() -> DomainUser:
        # Convert ORM User to domain User entity for tests
        return DomainUser.create_with_id(
            id=UserId(test_user.id),
            email=test_user.email,
            hashed_password=test_user.hashed_password,
            created_at=test_user.created_at,
            updated_at=test_user.updated_at,
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    # Always use local FileRepository in tests regardless of S3 env vars
    from src.core import container  # noqa: PLC0415
    from src.infrastructure.library.repositories.file_repository import (  # noqa: PLC0415
        FileRepository,
    )

    container.shared.file_repository.override(FileRepository())

    # The SAQ queue is wired in the app lifespan, which ASGITransport skips, so
    # provide a fake here. It returns string job keys so paths that persist a
    # JobBatch (e.g. the highlight-upload embedding enqueue) round-trip; tests
    # that assert enqueue behaviour override it again.
    job_key_counter = itertools.count()
    fake_queue_service = AsyncMock()
    fake_queue_service.enqueue = AsyncMock(
        side_effect=lambda *args, **kwargs: f"saq:test:{next(job_key_counter)}"
    )
    container.job_queue_service.override(fake_queue_service)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    container.job_queue_service.reset_override()
    container.shared.file_repository.reset_override()
    app.dependency_overrides.clear()


@pytest.fixture
async def test_book(db_session: AsyncSession, test_user: User) -> Book:
    """Create a standard test book."""
    return await create_test_book(
        db_session=db_session,
        user_id=test_user.id,
        title="Test Book",
        author="Test Author",
    )


@pytest.fixture
async def test_chapter(db_session: AsyncSession, test_book: Book) -> Chapter:
    """Create a standard test chapter attached to test_book."""
    chapter = Chapter(
        book_id=test_book.id,
        name="Test Chapter",
    )
    db_session.add(chapter)
    await db_session.commit()
    await db_session.refresh(chapter)
    return chapter


@pytest.fixture
async def test_highlight(db_session: AsyncSession, test_book: Book, test_user: User) -> Highlight:
    """Create a standard test highlight attached to test_book."""
    return await create_test_highlight(
        db_session=db_session,
        book=test_book,
        user_id=test_user.id,
        text="Test highlight text",
        page=10,
        datetime_str="2024-01-15 14:30:22",
    )


@pytest.fixture
async def test_flashcard(db_session: AsyncSession, test_book: Book, test_user: User) -> Flashcard:
    """Create a standard test flashcard attached to test_book."""
    flashcard = Flashcard(
        user_id=test_user.id,
        book_id=test_book.id,
        question="Test question",
        answer="Test answer",
    )
    db_session.add(flashcard)
    await db_session.commit()
    await db_session.refresh(flashcard)
    return flashcard


@pytest.fixture
async def test_tag_group(db_session: AsyncSession, test_book: Book) -> TagGroup:
    """Create a standard test tag group attached to test_book."""
    tag_group = TagGroup(book_id=test_book.id, name="Test Group")
    db_session.add(tag_group)
    await db_session.commit()
    await db_session.refresh(tag_group)
    return tag_group


@pytest.fixture
async def test_tag(db_session: AsyncSession, test_book: Book, test_user: User) -> Tag:
    """Create a standard test highlight tag attached to test_book."""
    tag = Tag(
        book_id=test_book.id,
        user_id=test_user.id,
        name="Test Tag",
    )
    db_session.add(tag)
    await db_session.commit()
    await db_session.refresh(tag)
    return tag


# Type alias for the book creation fixture (used across multiple test files)
CreateBookFunc = Callable[[dict[str, Any]], Awaitable[EreaderBookMetadata]]


@pytest.fixture
async def create_book_via_api(client: AsyncClient) -> CreateBookFunc:
    """Fixture factory for creating books via the API endpoint."""

    async def _create_book(book_data: dict[str, Any]) -> EreaderBookMetadata:
        response = await client.post("/api/v1/ereader/books", json=book_data)
        assert response.status_code == 200
        return EreaderBookMetadata(**response.json())

    return _create_book
