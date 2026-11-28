"""Read Chapter on the book details, measured from the Page Views of every session.

Reading speed is 60 characters a second, so a 600-character chapter needs 10
seconds on screen, and 80 % of it is 480 characters.
"""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Book, Chapter, PageView, ReadingSession, User
from tests.conftest import create_test_chapter, create_test_reading_session

FIRST_SESSION = datetime(2024, 1, 15, 10, tzinfo=UTC)


async def measure_book(
    db_session: AsyncSession, book: Book, total_characters: int | None, **starts: int | None
) -> dict[str, Chapter]:
    book.total_characters = total_characters
    chapters: dict[str, Chapter] = {}
    for number, (name, start_offset) in enumerate(starts.items(), start=1):
        chapter = await create_test_chapter(db_session, book, name, chapter_number=number)
        chapter.start_offset = start_offset
        chapters[name] = chapter
    await db_session.commit()
    return chapters


async def start_session(
    db_session: AsyncSession, book: Book, user_id: int | None = None, hours_later: int = 0
) -> ReadingSession:
    return await create_test_reading_session(
        db_session,
        book,
        user_id if user_id is not None else book.user_id,
        start_time=FIRST_SESSION + timedelta(hours=hours_later),
        minutes=50,
    )


async def view(
    db_session: AsyncSession, session: ReadingSession, start: int, end: int, seconds: float
) -> None:
    db_session.add(
        PageView(
            reading_session_id=session.id,
            start_xpoint="/body/DocFragment[1]/body/p[1]/text().0",
            end_xpoint="/body/DocFragment[1]/body/p[2]/text().0",
            start_position=[1, 0],
            end_position=[2, 0],
            start_offset=start,
            end_offset=end,
            position_source_hash="0" * 64,
            shown_at=session.start_time,
            duration_ms=round(seconds * 1000),
        )
    )
    await db_session.commit()


async def read_states(client: AsyncClient, book: Book) -> dict[str, str]:
    response = await client.get(f"/api/v1/books/{book.id}")
    assert response.status_code == 200, response.text
    return {chapter["name"]: chapter["read_state"] for chapter in response.json()["chapters"]}


@pytest.fixture
async def session(db_session: AsyncSession, test_book: Book) -> ReadingSession:
    return await start_session(db_session, test_book)


async def test_chapters_skipped_by_a_jump_ahead_stay_not_read(
    client: AsyncClient, db_session: AsyncSession, test_book: Book, session: ReadingSession
) -> None:
    await measure_book(db_session, test_book, 2400, One=0, Two=600, Three=1200, Four=1800)
    await view(db_session, session, 0, 600, seconds=10)
    await view(db_session, session, 1800, 2400, seconds=10)

    assert await read_states(client, test_book) == {
        "One": "read",
        "Two": "not_read",
        "Three": "not_read",
        "Four": "read",
    }


async def test_quick_flicking_through_the_same_text_never_adds_up(
    client: AsyncClient, db_session: AsyncSession, test_book: Book, session: ReadingSession
) -> None:
    await measure_book(db_session, test_book, 600, One=0)
    for _ in range(20):
        await view(db_session, session, 0, 600, seconds=9.9)

    assert await read_states(client, test_book) == {"One": "not_read"}


async def test_a_short_revisit_keeps_a_read_chapter_read(
    client: AsyncClient, db_session: AsyncSession, test_book: Book, session: ReadingSession
) -> None:
    await measure_book(db_session, test_book, 1200, One=0, Two=600)
    await view(db_session, session, 0, 600, seconds=10)
    await view(db_session, session, 600, 1200, seconds=10)
    revisit = await start_session(db_session, test_book, hours_later=1)
    await view(db_session, revisit, 0, 600, seconds=1)

    assert await read_states(client, test_book) == {"One": "read", "Two": "read"}


async def test_a_chapter_is_read_once_80_percent_of_its_text_was_read(
    client: AsyncClient, db_session: AsyncSession, test_book: Book, session: ReadingSession
) -> None:
    await measure_book(db_session, test_book, 1200, Short=0, Enough=600)
    await view(db_session, session, 0, 479, seconds=10)
    await view(db_session, session, 600, 1080, seconds=10)

    assert await read_states(client, test_book) == {"Short": "not_read", "Enough": "read"}


async def test_coverage_is_the_union_of_sessions_on_every_device(
    client: AsyncClient, db_session: AsyncSession, test_book: Book, session: ReadingSession
) -> None:
    await measure_book(db_session, test_book, 600, One=0)
    other_device = await start_session(db_session, test_book, hours_later=1)
    await view(db_session, session, 0, 400, seconds=7)
    await view(db_session, other_device, 300, 600, seconds=5)

    assert await read_states(client, test_book) == {"One": "read"}


async def test_reading_the_same_pages_twice_counts_them_once(
    client: AsyncClient, db_session: AsyncSession, test_book: Book, session: ReadingSession
) -> None:
    await measure_book(db_session, test_book, 600, One=0)
    await view(db_session, session, 0, 300, seconds=5)
    await view(db_session, session, 0, 300, seconds=5)

    assert await read_states(client, test_book) == {"One": "not_read"}


async def test_a_page_view_across_two_chapters_counts_towards_both(
    client: AsyncClient, db_session: AsyncSession, test_book: Book, session: ReadingSession
) -> None:
    await measure_book(db_session, test_book, 1200, One=0, Two=600)
    await view(db_session, session, 0, 450, seconds=8)
    await view(db_session, session, 500, 1100, seconds=10)

    assert await read_states(client, test_book) == {"One": "read", "Two": "read"}


async def test_a_parent_chapter_is_measured_on_its_text_before_its_first_child(
    client: AsyncClient, db_session: AsyncSession, test_book: Book, session: ReadingSession
) -> None:
    chapters = await measure_book(db_session, test_book, 700, Part=0, Child=100)
    chapters["Child"].parent_id = chapters["Part"].id
    await db_session.commit()
    await view(db_session, session, 0, 100, seconds=2)

    assert await read_states(client, test_book) == {"Part": "read", "Child": "not_read"}


async def test_a_chapter_with_no_text_of_its_own_is_unmeasurable(
    client: AsyncClient, db_session: AsyncSession, test_book: Book, session: ReadingSession
) -> None:
    await measure_book(db_session, test_book, 600, Plate=0, Unplaced=None, Text=0)
    await view(db_session, session, 0, 600, seconds=10)

    assert await read_states(client, test_book) == {
        "Plate": "unmeasurable",
        "Unplaced": "unmeasurable",
        "Text": "read",
    }


async def test_the_last_chapter_of_a_book_without_a_length_is_unmeasurable(
    client: AsyncClient, db_session: AsyncSession, test_book: Book, session: ReadingSession
) -> None:
    await measure_book(db_session, test_book, None, One=0, Two=600)
    await view(db_session, session, 0, 1200, seconds=20)

    assert await read_states(client, test_book) == {"One": "read", "Two": "unmeasurable"}


async def test_a_book_with_no_page_views_has_no_read_chapters(
    client: AsyncClient, db_session: AsyncSession, test_book: Book, session: ReadingSession
) -> None:
    await measure_book(db_session, test_book, 1200, One=0, Two=600)

    assert await read_states(client, test_book) == {"One": "not_read", "Two": "not_read"}


async def test_another_users_page_views_do_not_read_the_book(
    client: AsyncClient, db_session: AsyncSession, test_book: Book, other_user: User
) -> None:
    await measure_book(db_session, test_book, 600, One=0)
    theirs = await start_session(db_session, test_book, user_id=other_user.id)
    await view(db_session, theirs, 0, 600, seconds=10)

    assert await read_states(client, test_book) == {"One": "not_read"}
