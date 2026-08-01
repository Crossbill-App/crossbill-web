"""Tests for the reading-session-list read model."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.reading.services.label_resolution_service import LabelResolutionService
from src.domain.common.value_objects import XPointRange
from src.domain.common.value_objects.ids import BookId, UserId
from src.infrastructure.reading.queries.reading_session_query import ReadingSessionQuery
from src.models import Book, Highlight, ReadingSession, User
from tests.conftest import create_test_book, create_test_highlight

DEFAULT_USER_ID = 1
EPUB_BYTES = b"epub-bytes"
START_XPOINT = "/body/DocFragment[1]/body/div/p[1]/text().0"
END_XPOINT = "/body/DocFragment[1]/body/div/p[9]/text().10"


class FakeFileRepository:
    """Serves one canned EPUB and records what was asked for."""

    def __init__(self, epub: bytes | None = EPUB_BYTES) -> None:
        self.epub = epub
        self.requested: list[str | None] = []

    async def get_epub(self, filename: str | None) -> bytes | None:
        self.requested.append(filename)
        return self.epub


class FakeTextExtractionService:
    """Echoes back the range it was asked to extract."""

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    def extract_text(self, epub_content: bytes, start_xpoint: str, end_xpoint: str) -> str:
        self.calls += 1
        if self.fail:
            raise ValueError("malformed markup")
        return f"{start_xpoint}..{end_xpoint}"


@pytest.fixture
def file_repository() -> FakeFileRepository:
    return FakeFileRepository()


@pytest.fixture
def text_extraction_service() -> FakeTextExtractionService:
    return FakeTextExtractionService()


@pytest.fixture
def query(
    db_session: AsyncSession,
    label_resolution_service: LabelResolutionService,
    file_repository: FakeFileRepository,
    text_extraction_service: FakeTextExtractionService,
) -> ReadingSessionQuery:
    """The query service wired the way the container wires it."""
    return ReadingSessionQuery(
        db=db_session,
        label_resolution_service=label_resolution_service,
        file_repository=file_repository,  # pyright: ignore[reportArgumentType]
        text_extraction_service=text_extraction_service,  # pyright: ignore[reportArgumentType]
    )


async def add_epub(db_session: AsyncSession, book: Book) -> None:
    """Give a book an EPUB to extract from."""
    book.ebook_file = "book.epub"
    book.file_type = "epub"
    await db_session.commit()


async def add_session(
    db_session: AsyncSession,
    book: Book,
    user_id: int,
    start_time: datetime,
    *,
    with_xpoints: bool = True,
) -> ReadingSession:
    """Record a reading session for a book."""
    session = ReadingSession(
        user_id=user_id,
        book_id=book.id,
        start_time=start_time,
        end_time=start_time + timedelta(minutes=20),
        start_xpoint=START_XPOINT if with_xpoints else None,
        end_xpoint=END_XPOINT if with_xpoints else None,
        content_hash=f"hash-{start_time.isoformat()}-{book.id}",
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return session


async def link(db_session: AsyncSession, session: ReadingSession, highlight: Highlight) -> None:
    """Attach a highlight to a session."""
    session.highlights.append(highlight)
    await db_session.commit()


async def add_highlight(
    db_session: AsyncSession,
    book: Book,
    text: str,
    datetime_str: str,
    user_id: int = DEFAULT_USER_ID,
    deleted_at: datetime | None = None,
) -> Highlight:
    """A highlight on the book, owned by the default user unless told otherwise."""
    return await create_test_highlight(
        db_session=db_session,
        book=book,
        user_id=user_id,
        text=text,
        datetime_str=datetime_str,
        deleted_at=deleted_at,
    )


async def list_first_session_highlights(query: ReadingSessionQuery, book: Book) -> list[str]:
    """The highlight texts of the book's first (newest) session."""
    page = await query.list_for_book(BookId(book.id), UserId(DEFAULT_USER_ID), 30, 0)
    assert page is not None
    return [h.text for h in page.sessions[0].highlights]


async def test_missing_book_is_distinguished_from_a_book_without_sessions(
    query: ReadingSessionQuery, test_book: Book
) -> None:
    empty = await query.list_for_book(BookId(test_book.id), UserId(DEFAULT_USER_ID), 30, 0)
    assert empty is not None
    assert empty.sessions == ()
    assert empty.total == 0

    assert (
        await query.list_for_book(BookId(test_book.id + 999), UserId(DEFAULT_USER_ID), 30, 0)
        is None
    )


async def test_another_users_book_is_invisible(
    query: ReadingSessionQuery, test_book: Book, other_user: User
) -> None:
    assert await query.list_for_book(BookId(test_book.id), UserId(other_user.id), 30, 0) is None


async def test_sessions_are_paginated_newest_first_with_an_unpaginated_total(
    query: ReadingSessionQuery, db_session: AsyncSession, test_book: Book
) -> None:
    base = datetime(2024, 1, 1, tzinfo=UTC)
    for day in range(3):
        await add_session(db_session, test_book, DEFAULT_USER_ID, base + timedelta(days=day))

    page = await query.list_for_book(BookId(test_book.id), UserId(DEFAULT_USER_ID), 2, 1)

    assert page is not None
    assert page.total == 3
    assert [s.start_time.day for s in page.sessions] == [2, 1]


async def test_sessions_of_another_book_are_excluded(
    query: ReadingSessionQuery, db_session: AsyncSession, test_book: Book
) -> None:
    other_book = await create_test_book(
        db_session=db_session, user_id=DEFAULT_USER_ID, title="Other Book"
    )
    mine = await add_session(
        db_session, test_book, DEFAULT_USER_ID, datetime(2024, 1, 1, tzinfo=UTC)
    )
    await add_session(db_session, other_book, DEFAULT_USER_ID, datetime(2024, 1, 2, tzinfo=UTC))

    page = await query.list_for_book(BookId(test_book.id), UserId(DEFAULT_USER_ID), 30, 0)

    assert page is not None
    assert [s.id for s in page.sessions] == [mine.id]
    assert page.total == 1


async def test_soft_deleted_and_other_users_highlights_are_excluded(
    query: ReadingSessionQuery, db_session: AsyncSession, test_book: Book, other_user: User
) -> None:
    session = await add_session(
        db_session, test_book, DEFAULT_USER_ID, datetime(2024, 1, 1, tzinfo=UTC)
    )
    kept = await add_highlight(db_session, test_book, "Kept", "2024-01-01 10:00:00")
    deleted = await add_highlight(
        db_session, test_book, "Deleted", "2024-01-01 11:00:00", deleted_at=datetime.now(UTC)
    )
    theirs = await add_highlight(
        db_session, test_book, "Theirs", "2024-01-01 12:00:00", user_id=other_user.id
    )
    for highlight in (kept, deleted, theirs):
        await link(db_session, session, highlight)

    assert await list_first_session_highlights(query, test_book) == ["Kept"]


async def test_highlights_are_ordered_by_position_with_positionless_last(
    query: ReadingSessionQuery, db_session: AsyncSession, test_book: Book
) -> None:
    session = await add_session(
        db_session, test_book, DEFAULT_USER_ID, datetime(2024, 1, 1, tzinfo=UTC)
    )
    positions: list[list[int] | None] = [[9, 0], None, [2, 5], [2, 1]]
    for index, position in enumerate(positions):
        highlight = await add_highlight(
            db_session, test_book, f"Highlight {index}", f"2024-01-01 1{index}:00:00"
        )
        highlight.position = position
        await db_session.commit()
        await link(db_session, session, highlight)

    assert await list_first_session_highlights(query, test_book) == [
        "Highlight 3",
        "Highlight 2",
        "Highlight 0",
        "Highlight 1",
    ]


async def test_content_is_extracted_once_per_page_from_the_books_epub(
    query: ReadingSessionQuery,
    db_session: AsyncSession,
    test_book: Book,
    file_repository: FakeFileRepository,
    text_extraction_service: FakeTextExtractionService,
) -> None:
    await add_epub(db_session, test_book)
    base = datetime(2024, 1, 1, tzinfo=UTC)
    for day in range(2):
        await add_session(db_session, test_book, DEFAULT_USER_ID, base + timedelta(days=day))

    page = await query.list_for_book(BookId(test_book.id), UserId(DEFAULT_USER_ID), 30, 0)

    assert page is not None
    assert file_repository.requested == ["book.epub"]
    assert text_extraction_service.calls == 2
    # Extraction sees the xpoints round-tripped through XPointRange, not the
    # raw columns -- a zero offset loses its text() segment on the way back out.
    xpoints = XPointRange.parse(START_XPOINT, END_XPOINT)
    assert page.sessions[0].content == (f"{xpoints.start.to_string()}..{xpoints.end.to_string()}")


async def test_content_is_none_without_an_epub_or_without_a_recorded_range(
    query: ReadingSessionQuery,
    db_session: AsyncSession,
    test_book: Book,
    file_repository: FakeFileRepository,
) -> None:
    await add_session(db_session, test_book, DEFAULT_USER_ID, datetime(2024, 1, 1, tzinfo=UTC))

    page = await query.list_for_book(BookId(test_book.id), UserId(DEFAULT_USER_ID), 30, 0)
    assert page is not None
    assert page.sessions[0].content is None
    assert file_repository.requested == []

    await add_epub(db_session, test_book)
    await add_session(
        db_session,
        test_book,
        DEFAULT_USER_ID,
        datetime(2024, 1, 2, tzinfo=UTC),
        with_xpoints=False,
    )

    page = await query.list_for_book(BookId(test_book.id), UserId(DEFAULT_USER_ID), 30, 0)
    assert page is not None
    assert page.sessions[0].content is None


async def test_a_session_whose_extraction_fails_is_still_listed(
    db_session: AsyncSession,
    test_book: Book,
    label_resolution_service: LabelResolutionService,
    file_repository: FakeFileRepository,
) -> None:
    await add_epub(db_session, test_book)
    await add_session(db_session, test_book, DEFAULT_USER_ID, datetime(2024, 1, 1, tzinfo=UTC))
    query = ReadingSessionQuery(
        db=db_session,
        label_resolution_service=label_resolution_service,
        file_repository=file_repository,  # pyright: ignore[reportArgumentType]
        text_extraction_service=FakeTextExtractionService(fail=True),  # pyright: ignore[reportArgumentType]
    )

    page = await query.list_for_book(BookId(test_book.id), UserId(DEFAULT_USER_ID), 30, 0)

    assert page is not None
    assert len(page.sessions) == 1
    assert page.sessions[0].content is None
