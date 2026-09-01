"""Tests for the library-wide reading-activity API endpoint."""

from datetime import UTC, date, datetime
from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.models import Book, User
from tests.conftest import create_test_book, create_test_reading_session, readers_today

DEFAULT_USER_ID = 1
OTHER_USER_ID = 2

# Every fixture below is read in March 2024, which a today in June 2024 keeps
# inside the window.
RECENTLY = date(2024, 6, 1)


async def get_activity(client: AsyncClient, params: dict[str, str] | None = None) -> dict[str, Any]:
    """Read the reader's activity grid, asserting the request succeeded."""
    response = await client.get("/api/v1/statistics/reading-activity", params=params)
    assert response.status_code == status.HTTP_200_OK
    return response.json()


async def emma(db_session: AsyncSession, user_id: int = DEFAULT_USER_ID) -> Book:
    """A second book, so that a day can be made of more than one."""
    return await create_test_book(db_session=db_session, user_id=user_id, title="Emma")


async def read(
    db_session: AsyncSession,
    book: Book,
    at: datetime,
    pages: int | None = None,
    user_id: int = DEFAULT_USER_ID,
) -> None:
    """Record a session that got through ``pages``, or none for an xpoint-only book."""
    await create_test_reading_session(
        db_session,
        book,
        user_id,
        at,
        start_page=None if pages is None else 0,
        end_page=pages,
    )


def titles_by_day(body: dict[str, Any]) -> dict[str, list[str]]:
    """The grid as ``{day: [title]}``, which is what the reader is shown."""
    titles = {book["id"]: book["title"] for book in body["activity"]["books"]}
    return {
        day["date"]: [titles[book_id] for book_id in day["book_ids"]]
        for day in body["activity"]["days"]
    }


class TestGetLibraryReadingActivity:
    """GET /api/v1/statistics/reading-activity."""

    async def test_a_day_adds_up_every_book_read_on_it(
        self, client: AsyncClient, db_session: AsyncSession, test_book: Book
    ) -> None:
        other_book = await emma(db_session)
        await read(db_session, test_book, datetime(2024, 3, 1, 20, tzinfo=UTC), pages=10)
        await read(db_session, other_book, datetime(2024, 3, 1, 8, tzinfo=UTC), pages=30)

        with readers_today(RECENTLY):
            body = await get_activity(client)

        activity = body["activity"]
        assert activity["unit"] == "pages"
        assert activity["range_start"] == "2023-06-03"
        assert activity["range_end"] == "2024-06-01"
        assert activity["days"] == [
            {
                "date": "2024-03-01",
                "value": 40,
                "level": 2,
                "book_ids": [other_book.id, test_book.id],
            }
        ]
        assert titles_by_day(body) == {"2024-03-01": ["Emma", "Test Book"]}

    async def test_a_reader_with_no_reading_has_no_grid(
        self, client: AsyncClient, test_book: Book
    ) -> None:
        """An empty library is an answer, not a 404: the landing page simply shows nothing."""
        with readers_today(RECENTLY):
            body = await get_activity(client)

        assert body == {"activity": None, "stats": None}

    async def test_another_readers_books_are_not_on_the_grid(
        self, client: AsyncClient, db_session: AsyncSession, test_book: Book
    ) -> None:
        db_session.add(User(id=OTHER_USER_ID, email="other@test.com"))
        await db_session.commit()
        their_book = await emma(db_session, user_id=OTHER_USER_ID)
        await read(
            db_session,
            their_book,
            datetime(2024, 3, 1, 20, tzinfo=UTC),
            pages=500,
            user_id=OTHER_USER_ID,
        )
        await read(db_session, test_book, datetime(2024, 3, 2, 20, tzinfo=UTC), pages=10)

        with readers_today(RECENTLY):
            body = await get_activity(client)

        assert titles_by_day(body) == {"2024-03-02": ["Test Book"]}
        assert [book["id"] for book in body["activity"]["books"]] == [test_book.id]
        assert body["stats"]["books_read"] == 1
        assert body["stats"]["total_seconds"] == 20 * 60

    async def test_the_numbers_sum_the_year_the_grid_draws(
        self, client: AsyncClient, db_session: AsyncSession, test_book: Book
    ) -> None:
        """The stats beside the grid count the same days, in the same window."""
        other_book = await emma(db_session)
        # Yesterday and the day before, so that a streak the reader has not yet
        # added to today is still a streak.
        await read(db_session, test_book, datetime(2024, 5, 31, 20, tzinfo=UTC), pages=10)
        await read(db_session, other_book, datetime(2024, 5, 30, 20, tzinfo=UTC), pages=30)
        # A session from before the window opened, on neither square nor total.
        await read(db_session, test_book, datetime(2022, 1, 1, 20, tzinfo=UTC), pages=50)

        with readers_today(RECENTLY):
            body = await get_activity(client)

        assert body["stats"] == {
            "last_read": "2024-05-31",
            "seconds_today": 0,
            "total_seconds": 2 * 20 * 60,
            "streak_days": 2,
            "days_read": 2,
            "books_read": 2,
        }

    async def test_todays_reading_is_counted_in_the_readers_own_timezone(
        self, client: AsyncClient, db_session: AsyncSession, test_book: Book
    ) -> None:
        """22:15 UTC on 31 May is already 1 June in Helsinki -- the reader's today."""
        await read(db_session, test_book, datetime(2024, 5, 31, 22, 15, tzinfo=UTC), pages=10)

        with readers_today(RECENTLY):
            in_utc = await get_activity(client)
            in_helsinki = await get_activity(client, {"tz": "Europe/Helsinki"})

        assert in_utc["stats"]["seconds_today"] == 0
        assert in_helsinki["stats"]["seconds_today"] == 20 * 60

    async def test_the_days_are_counted_in_the_requested_timezone(
        self, client: AsyncClient, db_session: AsyncSession, test_book: Book
    ) -> None:
        """22:15 UTC is the next morning in Helsinki, so the two books share a day there."""
        other_book = await emma(db_session)
        await read(db_session, test_book, datetime(2024, 3, 15, 22, 15, tzinfo=UTC), pages=10)
        await read(db_session, other_book, datetime(2024, 3, 16, 5, 0, tzinfo=UTC), pages=20)

        with readers_today(RECENTLY):
            in_utc = await get_activity(client)
            in_helsinki = await get_activity(client, {"tz": "Europe/Helsinki"})

        assert titles_by_day(in_utc) == {"2024-03-15": ["Test Book"], "2024-03-16": ["Emma"]}
        assert titles_by_day(in_helsinki) == {"2024-03-16": ["Test Book", "Emma"]}

    async def test_a_book_read_without_page_numbers_is_named_on_a_day_that_counted(
        self, client: AsyncClient, db_session: AsyncSession, test_book: Book
    ) -> None:
        """One xpoint-only book must not put the whole library's year in minutes."""
        other_book = await emma(db_session)
        await read(db_session, test_book, datetime(2024, 3, 1, 20, tzinfo=UTC), pages=10)
        await read(db_session, other_book, datetime(2024, 3, 1, 8, tzinfo=UTC))

        with readers_today(RECENTLY):
            body = await get_activity(client)

        assert body["activity"]["unit"] == "pages"
        assert body["activity"]["days"][0]["value"] == 10
        assert titles_by_day(body) == {"2024-03-01": ["Emma", "Test Book"]}
