"""Tests for the book-reading-statistics read model."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.reading.services.reading_statistics_calculator import ReadingStatisticsCalculator
from src.infrastructure.reading.queries.book_statistics_query import BookStatisticsQuery
from src.models import Book, User
from tests.conftest import create_test_book, create_test_reading_session

DEFAULT_USER_ID = 1


@pytest.fixture
def query(db_session: AsyncSession) -> BookStatisticsQuery:
    """The query service wired the way the container wires it."""
    return BookStatisticsQuery(db=db_session, statistics_calculator=ReadingStatisticsCalculator())


async def set_end_position(db_session: AsyncSession, book: Book, position: list[int]) -> None:
    """Give the book the end position progress is measured against."""
    book.end_position = position
    await db_session.commit()


async def test_missing_book_is_distinguished_from_a_book_without_sessions(
    query: BookStatisticsQuery, test_book: Book
) -> None:
    empty = await query.get_statistics(BookId(test_book.id), UserId(DEFAULT_USER_ID), UTC)
    assert empty is not None
    assert empty.session_count == 0
    assert empty.total_reading_seconds == 0

    missing = await query.get_statistics(BookId(test_book.id + 999), UserId(DEFAULT_USER_ID), UTC)
    assert missing is None


async def test_another_users_book_is_invisible(
    query: BookStatisticsQuery, test_book: Book, other_user: User
) -> None:
    assert await query.get_statistics(BookId(test_book.id), UserId(other_user.id), UTC) is None


async def test_sessions_are_summed_across_the_book(
    query: BookStatisticsQuery, db_session: AsyncSession, test_book: Book
) -> None:
    await create_test_reading_session(
        db_session, test_book, DEFAULT_USER_ID, datetime(2024, 1, 1, 20, tzinfo=UTC), minutes=30
    )
    await create_test_reading_session(
        db_session, test_book, DEFAULT_USER_ID, datetime(2024, 1, 5, 20, tzinfo=UTC), minutes=10
    )

    statistics = await query.get_statistics(BookId(test_book.id), UserId(DEFAULT_USER_ID), UTC)

    assert statistics is not None
    assert statistics.session_count == 2
    assert statistics.total_reading_seconds == 40 * 60
    assert statistics.average_session_seconds == 20 * 60
    assert statistics.span_days == 5


async def test_sessions_of_another_book_or_another_user_are_excluded(
    query: BookStatisticsQuery, db_session: AsyncSession, test_book: Book, other_user: User
) -> None:
    other_book = await create_test_book(
        db_session=db_session, user_id=DEFAULT_USER_ID, title="Other Book"
    )
    await create_test_reading_session(
        db_session, test_book, DEFAULT_USER_ID, datetime(2024, 1, 1, 20, tzinfo=UTC), minutes=30
    )
    await create_test_reading_session(
        db_session, other_book, DEFAULT_USER_ID, datetime(2024, 1, 2, 20, tzinfo=UTC), minutes=30
    )
    await create_test_reading_session(
        db_session, test_book, other_user.id, datetime(2024, 1, 3, 20, tzinfo=UTC), minutes=30
    )

    statistics = await query.get_statistics(BookId(test_book.id), UserId(DEFAULT_USER_ID), UTC)

    assert statistics is not None
    assert statistics.session_count == 1
    assert statistics.total_reading_seconds == 30 * 60


async def test_progress_is_measured_from_the_latest_sessions_end_position(
    query: BookStatisticsQuery, db_session: AsyncSession, test_book: Book
) -> None:
    await set_end_position(db_session, test_book, [200, 0])
    await create_test_reading_session(
        db_session,
        test_book,
        DEFAULT_USER_ID,
        datetime(2024, 1, 1, 20, tzinfo=UTC),
        end_position=[20, 0],
    )
    await create_test_reading_session(
        db_session,
        test_book,
        DEFAULT_USER_ID,
        datetime(2024, 1, 2, 20, tzinfo=UTC),
        end_position=[150, 0],
    )

    statistics = await query.get_statistics(BookId(test_book.id), UserId(DEFAULT_USER_ID), UTC)

    assert statistics is not None
    assert statistics.progress_percent == 75


async def test_progress_is_unknown_while_the_book_has_no_end_position(
    query: BookStatisticsQuery, db_session: AsyncSession, test_book: Book
) -> None:
    await create_test_reading_session(
        db_session,
        test_book,
        DEFAULT_USER_ID,
        datetime(2024, 1, 1, 20, tzinfo=UTC),
        end_position=[20, 0],
    )

    statistics = await query.get_statistics(BookId(test_book.id), UserId(DEFAULT_USER_ID), UTC)

    assert statistics is not None
    assert statistics.progress_percent is None
