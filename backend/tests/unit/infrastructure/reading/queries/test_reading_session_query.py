"""Tests for the reading-session-list read model."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.reading.services.label_resolution_service import LabelResolutionService
from src.domain.common.value_objects.ids import BookId, UserId
from src.infrastructure.reading.queries.reading_session_query import ReadingSessionQuery
from src.models import Book, Highlight, ReadingSession, User
from tests.conftest import create_test_book, create_test_highlight

DEFAULT_USER_ID = 1
START_XPOINT = "/body/DocFragment[1]/body/div/p[1]/text().0"
END_XPOINT = "/body/DocFragment[1]/body/div/p[9]/text().10"


@pytest.fixture
def query(
    db_session: AsyncSession,
    label_resolution_service: LabelResolutionService,
) -> ReadingSessionQuery:
    """The query service wired the way the container wires it."""
    return ReadingSessionQuery(
        db=db_session,
        label_resolution_service=label_resolution_service,
    )


async def add_session(
    db_session: AsyncSession,
    book: Book,
    user_id: int,
    start_time: datetime,
) -> ReadingSession:
    """Record a reading session for a book."""
    session = ReadingSession(
        user_id=user_id,
        book_id=book.id,
        start_time=start_time,
        end_time=start_time + timedelta(minutes=20),
        start_xpoint=START_XPOINT,
        end_xpoint=END_XPOINT,
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
