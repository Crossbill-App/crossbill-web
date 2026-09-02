"""Tests for the landing page's feed of recent highlights and notes."""

from datetime import UTC, datetime
from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src import models
from src.models import Book, User
from tests.conftest import (
    create_test_book,
    create_test_chapter,
    create_test_highlight,
    create_test_highlight_style,
)

DEFAULT_USER_ID = 1
OTHER_USER_ID = 2


async def get_captures(
    client: AsyncClient, params: dict[str, str | int] | None = None
) -> list[dict[str, Any]]:
    """Read the capture feed, asserting the request succeeded."""
    response = await client.get("/api/v1/captures/recent", params=params)
    assert response.status_code == status.HTTP_200_OK
    return response.json()["items"]


async def note(
    db_session: AsyncSession,
    book: Book,
    title: str,
    created: datetime,
    updated: datetime | None = None,
    kind: str | None = "concept",
    body: str = "",
    user_id: int = DEFAULT_USER_ID,
) -> models.Note:
    """Write a note with both its timestamps under the test's control."""
    written = models.Note(
        user_id=user_id,
        title=title,
        body=body,
        kind=kind,
        created_at=created,
        updated_at=updated or created,
    )
    written.books.append(book)
    db_session.add(written)
    await db_session.commit()
    await db_session.refresh(written)
    return written


def titles(captures: list[dict[str, Any]]) -> list[str]:
    """What the feed shows, in order: a note by its title, a highlight by its text."""
    return [capture["title"] or capture["text"] for capture in captures]


class TestRecentCaptures:
    """The feed's ordering, grouping and contents."""

    async def test_highlights_and_notes_share_one_timeline(
        self, client: AsyncClient, db_session: AsyncSession, test_book: Book, test_user: User
    ) -> None:
        emma = await create_test_book(db_session, test_user.id, title="Emma")
        await create_test_highlight(
            db_session, test_book, test_user.id, "older highlight", "2026-08-30 09:00:00"
        )
        await note(
            db_session, emma, "A note between them", datetime(2026, 8, 30, 12, 0, tzinfo=UTC)
        )
        await create_test_highlight(
            db_session, emma, test_user.id, "newest highlight", "2026-08-30 20:00:00"
        )

        captures = await get_captures(client)

        assert titles(captures) == ["newest highlight", "A note between them", "older highlight"]
        assert [capture["kind"] for capture in captures] == ["highlight", "note", "highlight"]

    async def test_a_capture_carries_where_it_came_from(
        self, client: AsyncClient, db_session: AsyncSession, test_book: Book, test_user: User
    ) -> None:
        chapter = await create_test_chapter(db_session, test_book, name="Chapter One")
        style = await create_test_highlight_style(
            db_session,
            user_id=test_user.id,
            book_id=test_book.id,
            label="Worth returning to",
            ui_color="#eb5757",
        )
        await create_test_highlight(
            db_session,
            test_book,
            test_user.id,
            "a passage",
            "2026-08-30 09:00:00",
            page=214,
            chapter_id=chapter.id,
            highlight_style_id=style.id,
        )

        (capture,) = await get_captures(client)

        assert capture["book_title"] == test_book.title
        assert capture["chapter_name"] == "Chapter One"
        assert capture["page"] == 214
        assert capture["captured_at"] == "2026-08-30T09:00:00"
        assert capture["day"] == "2026-08-30"
        assert capture["label"]["text"] == "Worth returning to"
        assert capture["label"]["ui_color"] == "#eb5757"

    async def test_a_note_carries_its_kind_and_body(
        self, client: AsyncClient, db_session: AsyncSession, test_book: Book
    ) -> None:
        await note(
            db_session,
            test_book,
            "Koskela",
            datetime(2026, 8, 30, 19, 5, tzinfo=UTC),
            kind="character",
            body="Quiet authority.",
        )

        (capture,) = await get_captures(client)

        assert capture["kind"] == "note"
        assert capture["note_kind"] == "character"
        assert capture["text"] == "Quiet authority."
        assert capture["chapter_name"] is None
        assert capture["label"] is None

    async def test_one_book_gives_a_day_three_captures_and_says_what_it_holds_back(
        self, client: AsyncClient, db_session: AsyncSession, test_book: Book, test_user: User
    ) -> None:
        for hour in range(6):
            await create_test_highlight(
                db_session,
                test_book,
                test_user.id,
                f"highlight at {hour}",
                f"2026-08-30 {hour + 10:02d}:00:00",
            )

        captures = await get_captures(client)

        assert titles(captures) == ["highlight at 5", "highlight at 4", "highlight at 3"]
        assert [capture["more_in_book"] for capture in captures] == [0, 0, 3]

    async def test_the_cap_is_counted_a_day_at_a_time(
        self, client: AsyncClient, db_session: AsyncSession, test_book: Book, test_user: User
    ) -> None:
        for day in ("2026-08-29", "2026-08-30"):
            for hour in range(4):
                await create_test_highlight(
                    db_session,
                    test_book,
                    test_user.id,
                    f"{day} at {hour}",
                    f"{day} {hour + 10:02d}:00:00",
                )

        captures = await get_captures(client)

        assert [capture["day"] for capture in captures] == [
            "2026-08-30",
            "2026-08-30",
            "2026-08-30",
            "2026-08-29",
            "2026-08-29",
            "2026-08-29",
        ]
        assert [capture["more_in_book"] for capture in captures] == [0, 0, 1, 0, 0, 1]

    async def test_the_remainder_counts_what_the_feed_leaves_out_not_what_the_cap_did(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        for index in range(3):
            book = await create_test_book(db_session, test_user.id, title=f"Book {index}")
            for hour in range(4):
                await create_test_highlight(
                    db_session,
                    book,
                    test_user.id,
                    f"book {index} at {hour}",
                    f"2026-08-30 {hour + 10:02d}:00:00",
                )

        captures = await get_captures(client, {"limit": 3})

        # One row per book, so the row the cap stopped at is itself left out.
        assert [capture["book_title"] for capture in captures] == ["Book 2", "Book 1", "Book 0"]
        assert [capture["more_in_book"] for capture in captures] == [3, 3, 3]

    async def test_highlights_and_notes_are_counted_apart(
        self, client: AsyncClient, db_session: AsyncSession, test_book: Book, test_user: User
    ) -> None:
        for hour in (9, 10):
            await create_test_highlight(
                db_session,
                test_book,
                test_user.id,
                f"highlight at {hour}",
                f"2026-08-30 {hour:02d}:00:00",
            )
        for hour in (11, 12, 13, 14):
            await note(
                db_session, test_book, f"note at {hour}", datetime(2026, 8, 30, hour, tzinfo=UTC)
            )

        captures = await get_captures(client)

        # The day's four notes take every row the cap allows, so the count is
        # the one note left over rather than the two unshown highlights.
        assert titles(captures) == ["note at 14", "note at 13", "note at 12"]
        assert [capture["more_in_book"] for capture in captures] == [0, 0, 1]

    async def test_an_edited_note_returns_to_the_top(
        self, client: AsyncClient, db_session: AsyncSession, test_book: Book, test_user: User
    ) -> None:
        await create_test_highlight(
            db_session, test_book, test_user.id, "yesterday's highlight", "2026-08-30 09:00:00"
        )
        await note(
            db_session,
            test_book,
            "Rewritten today",
            created=datetime(2026, 6, 1, 9, 0, tzinfo=UTC),
            updated=datetime(2026, 8, 31, 9, 0, tzinfo=UTC),
        )

        captures = await get_captures(client)

        assert titles(captures) == ["Rewritten today", "yesterday's highlight"]
        assert captures[0]["day"] == "2026-08-31"

    async def test_an_edited_highlight_stays_where_it_was_made(
        self, client: AsyncClient, db_session: AsyncSession, test_book: Book, test_user: User
    ) -> None:
        edited = await create_test_highlight(
            db_session, test_book, test_user.id, "marked in June", "2026-06-01 09:00:00"
        )
        edited.koreader_updated_at = datetime(2026, 8, 31, 9, 0)  # noqa: DTZ001 - a device clock
        await db_session.commit()
        await note(db_session, test_book, "A later note", datetime(2026, 7, 1, 9, 0, tzinfo=UTC))

        captures = await get_captures(client)

        assert titles(captures) == ["A later note", "marked in June"]
        assert captures[1]["day"] == "2026-06-01"

    async def test_gists_are_not_captures(
        self, client: AsyncClient, db_session: AsyncSession, test_book: Book
    ) -> None:
        await note(
            db_session,
            test_book,
            "Machine-written gist",
            datetime(2026, 8, 30, 12, 0, tzinfo=UTC),
            kind="gist",
        )
        await note(
            db_session,
            test_book,
            "An untyped note",
            datetime(2026, 8, 29, 12, 0, tzinfo=UTC),
            kind=None,
        )

        captures = await get_captures(client)

        assert titles(captures) == ["An untyped note"]

    async def test_deleted_highlights_are_gone_but_device_removals_are_not(
        self, client: AsyncClient, db_session: AsyncSession, test_book: Book, test_user: User
    ) -> None:
        await create_test_highlight(
            db_session,
            test_book,
            test_user.id,
            "deleted",
            "2026-08-30 12:00:00",
            deleted_at=datetime(2026, 8, 31, tzinfo=UTC),
        )
        await create_test_highlight(
            db_session,
            test_book,
            test_user.id,
            "no longer on the device",
            "2026-08-30 11:00:00",
            removed_from_devices_at=datetime(2026, 8, 31, tzinfo=UTC),
        )

        captures = await get_captures(client)

        assert titles(captures) == ["no longer on the device"]

    async def test_a_note_falls_on_the_day_the_reader_is_living(
        self, client: AsyncClient, db_session: AsyncSession, test_book: Book
    ) -> None:
        await note(db_session, test_book, "Late one", datetime(2026, 8, 30, 22, 30, tzinfo=UTC))

        (in_utc,) = await get_captures(client)
        (in_helsinki,) = await get_captures(client, {"tz": "Europe/Helsinki"})

        assert in_utc["day"] == "2026-08-30"
        assert in_utc["captured_at"] == "2026-08-30T22:30:00"
        assert in_helsinki["day"] == "2026-08-31"
        assert in_helsinki["captured_at"] == "2026-08-31T01:30:00"

    async def test_another_readers_captures_are_invisible(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        db_session.add(models.User(id=OTHER_USER_ID, email="other@test.com"))
        await db_session.commit()
        theirs = await create_test_book(db_session, OTHER_USER_ID, title="Their book")
        await create_test_highlight(
            db_session, theirs, OTHER_USER_ID, "their highlight", "2026-08-30 12:00:00"
        )
        await note(
            db_session,
            theirs,
            "their note",
            datetime(2026, 8, 30, 13, 0, tzinfo=UTC),
            user_id=OTHER_USER_ID,
        )

        assert await get_captures(client) == []

    async def test_the_feed_stops_at_the_limit(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        for index in range(4):
            book = await create_test_book(db_session, test_user.id, title=f"Book {index}")
            await create_test_highlight(
                db_session, book, test_user.id, f"highlight {index}", f"2026-08-30 1{index}:00:00"
            )

        captures = await get_captures(client, {"limit": 2})

        assert titles(captures) == ["highlight 3", "highlight 2"]

    async def test_a_reader_with_nothing_captured_gets_an_empty_feed(
        self, client: AsyncClient
    ) -> None:
        assert await get_captures(client) == []
