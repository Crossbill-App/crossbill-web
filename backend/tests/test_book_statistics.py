"""Tests for the book reading-statistics API endpoint."""

from datetime import UTC, datetime
from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.models import Book, User
from tests.conftest import create_test_book, create_test_reading_session

DEFAULT_USER_ID = 1
OTHER_USER_ID = 2


async def get_statistics(
    client: AsyncClient, book_id: int, params: dict[str, str] | None = None
) -> dict[str, Any]:
    """Read a book's statistics, asserting the request succeeded."""
    response = await client.get(f"/api/v1/books/{book_id}/statistics", params=params)
    assert response.status_code == status.HTTP_200_OK
    return response.json()


async def add_sessions_either_side_of_utc_midnight(db_session: AsyncSession, book: Book) -> None:
    """Two sessions at 00:15 and 07:00 on 16 March in Helsinki -- 15 and 16 March in UTC."""
    await create_test_reading_session(
        db_session, book, DEFAULT_USER_ID, datetime(2024, 3, 15, 22, 15, tzinfo=UTC)
    )
    await create_test_reading_session(
        db_session, book, DEFAULT_USER_ID, datetime(2024, 3, 16, 5, 0, tzinfo=UTC)
    )


class TestGetBookStatistics:
    """GET /api/v1/books/{book_id}/statistics."""

    async def test_totals_every_session_of_the_book(
        self, client: AsyncClient, db_session: AsyncSession, test_book: Book
    ) -> None:
        test_book.end_position = [400, 0]
        await db_session.commit()
        await create_test_reading_session(
            db_session, test_book, DEFAULT_USER_ID, datetime(2024, 3, 1, 20, tzinfo=UTC), minutes=30
        )
        await create_test_reading_session(
            db_session,
            test_book,
            DEFAULT_USER_ID,
            datetime(2024, 3, 4, 20, tzinfo=UTC),
            minutes=50,
            end_position=[300, 0],
        )

        body = await get_statistics(client, test_book.id)

        assert body["session_count"] == 2
        assert body["total_reading_seconds"] == 80 * 60
        assert body["average_session_seconds"] == 40 * 60
        assert body["first_session_start"].startswith("2024-03-01T20:00:00")
        assert body["last_session_end"].startswith("2024-03-04T20:50:00")
        assert body["span_days"] == 4
        assert body["progress_percent"] == 75

    async def test_a_book_nobody_has_opened_reports_nothing_rather_than_failing(
        self, client: AsyncClient, test_book: Book
    ) -> None:
        body = await get_statistics(client, test_book.id)

        assert body["session_count"] == 0
        assert body["total_reading_seconds"] == 0
        assert body["average_session_seconds"] is None
        assert body["first_session_start"] is None
        assert body["last_session_end"] is None
        assert body["span_days"] is None
        assert body["progress_percent"] is None

    async def test_another_users_book_is_not_found(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        db_session.add(User(id=OTHER_USER_ID, email="other@test.com"))
        await db_session.commit()
        their_book = await create_test_book(
            db_session=db_session, user_id=OTHER_USER_ID, title="Their Book"
        )
        await create_test_reading_session(
            db_session, their_book, OTHER_USER_ID, datetime(2024, 3, 1, 20, tzinfo=UTC)
        )

        response = await client.get(f"/api/v1/books/{their_book.id}/statistics")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_a_missing_book_is_not_found(self, client: AsyncClient, test_book: Book) -> None:
        response = await client.get(f"/api/v1/books/{test_book.id + 999}/statistics")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_the_span_is_counted_in_the_requested_timezone(
        self, client: AsyncClient, db_session: AsyncSession, test_book: Book
    ) -> None:
        await add_sessions_either_side_of_utc_midnight(db_session, test_book)

        assert (await get_statistics(client, test_book.id))["span_days"] == 2
        helsinki = await get_statistics(client, test_book.id, {"tz": "Europe/Helsinki"})
        assert helsinki["span_days"] == 1

    async def test_an_unknown_timezone_falls_back_to_utc_rather_than_failing(
        self, client: AsyncClient, db_session: AsyncSession, test_book: Book
    ) -> None:
        await add_sessions_either_side_of_utc_midnight(db_session, test_book)

        body = await get_statistics(client, test_book.id, {"tz": "Mars/Olympus_Mons"})

        assert body["span_days"] == 2

    async def test_a_timezone_no_filesystem_could_hold_falls_back_to_utc_too(
        self, client: AsyncClient, db_session: AsyncSession, test_book: Book
    ) -> None:
        """A name too long to be a path fails the lookup differently, and must not 500."""
        await add_sessions_either_side_of_utc_midnight(db_session, test_book)

        body = await get_statistics(client, test_book.id, {"tz": "a" * 10_000})

        assert body["span_days"] == 2
