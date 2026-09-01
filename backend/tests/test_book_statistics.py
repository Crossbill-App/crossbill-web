"""Tests for the book reading-statistics API endpoint."""

from datetime import UTC, date, datetime
from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.models import Book, User
from tests.conftest import create_test_book, create_test_reading_session, readers_today

DEFAULT_USER_ID = 1
OTHER_USER_ID = 2


async def add_three_days_of_paged_reading(db_session: AsyncSession, book: Book) -> None:
    """10, 30 and 60 pages on consecutive days -- a median of 30, so cuts at 15 and 45."""
    for day, (start_page, end_page) in enumerate([(0, 10), (10, 40), (40, 100)], start=1):
        await create_test_reading_session(
            db_session,
            book,
            DEFAULT_USER_ID,
            datetime(2024, 3, day, 20, tzinfo=UTC),
            start_page=start_page,
            end_page=end_page,
        )


async def get_statistics(
    client: AsyncClient, book_id: int, params: dict[str, str] | None = None
) -> dict[str, Any]:
    """Read a book's statistics, asserting the request succeeded."""
    response = await client.get(f"/api/v1/books/{book_id}/statistics", params=params)
    assert response.status_code == status.HTTP_200_OK
    return response.json()


async def assert_not_found(client: AsyncClient, book_id: int) -> None:
    """Read a book's statistics, asserting the app's stable 404 answered instead.

    The payload matters as much as the status: it is what the client branches
    on, and it must name no book the caller cannot see.
    """
    response = await client.get(f"/api/v1/books/{book_id}/statistics")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {
        "error": "not_found",
        "message": "The requested resource was not found.",
    }


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

        await assert_not_found(client, their_book.id)

    async def test_a_missing_book_is_not_found(self, client: AsyncClient, test_book: Book) -> None:
        await assert_not_found(client, test_book.id + 999)

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


class TestBookActivityGrid:
    """The daily activity grid carried by GET /api/v1/books/{book_id}/statistics."""

    async def test_days_are_coloured_against_this_books_typical_day(
        self, client: AsyncClient, db_session: AsyncSession, test_book: Book
    ) -> None:
        await add_three_days_of_paged_reading(db_session, test_book)

        activity = (await get_statistics(client, test_book.id))["activity"]

        assert activity["unit"] == "pages"
        assert activity["days"] == [
            {"date": "2024-03-01", "value": 10, "level": 1},
            {"date": "2024-03-02", "value": 30, "level": 2},
            {"date": "2024-03-03", "value": 60, "level": 4},
        ]

    async def test_the_grid_spans_a_year_ending_on_the_last_day_read(
        self, client: AsyncClient, db_session: AsyncSession, test_book: Book
    ) -> None:
        """This book was last read long before today, so today would be a year of nothing."""
        await add_three_days_of_paged_reading(db_session, test_book)

        activity = (await get_statistics(client, test_book.id))["activity"]

        assert activity["range_end"] == "2024-03-03"
        assert activity["range_start"] == "2023-03-05"

    async def test_the_grid_ends_on_the_readers_today_for_a_book_still_being_read(
        self, client: AsyncClient, db_session: AsyncSession, test_book: Book
    ) -> None:
        """So the fortnight since the last session shows as the gap it is."""
        await add_three_days_of_paged_reading(db_session, test_book)

        with readers_today(date(2024, 3, 17)):
            activity = (await get_statistics(client, test_book.id))["activity"]

        assert activity["range_end"] == "2024-03-17"
        assert activity["range_start"] == "2023-03-19"
        assert [day["date"] for day in activity["days"]] == [
            "2024-03-01",
            "2024-03-02",
            "2024-03-03",
        ]

    async def test_a_book_without_page_numbers_is_measured_in_minutes(
        self, client: AsyncClient, db_session: AsyncSession, test_book: Book
    ) -> None:
        """One session synced by xpoint alone puts the whole book on minutes."""
        await add_three_days_of_paged_reading(db_session, test_book)
        await create_test_reading_session(
            db_session, test_book, DEFAULT_USER_ID, datetime(2024, 3, 4, 20, tzinfo=UTC), minutes=45
        )

        activity = (await get_statistics(client, test_book.id))["activity"]

        assert activity["unit"] == "minutes"
        assert [day["value"] for day in activity["days"]] == [20, 20, 20, 45]

    async def test_days_are_bucketed_in_the_requested_timezone(
        self, client: AsyncClient, db_session: AsyncSession, test_book: Book
    ) -> None:
        await add_sessions_either_side_of_utc_midnight(db_session, test_book)

        in_utc = (await get_statistics(client, test_book.id))["activity"]
        in_helsinki = (await get_statistics(client, test_book.id, {"tz": "Europe/Helsinki"}))[
            "activity"
        ]

        assert [day["date"] for day in in_utc["days"]] == ["2024-03-15", "2024-03-16"]
        assert in_helsinki["days"] == [{"date": "2024-03-16", "value": 40, "level": 2}]

    async def test_a_book_nobody_has_opened_has_no_grid(
        self, client: AsyncClient, test_book: Book
    ) -> None:
        assert (await get_statistics(client, test_book.id))["activity"] is None
