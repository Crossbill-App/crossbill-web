"""Tests for the ereader chapter-prereading read model."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.common.value_objects.ids import UserId
from src.infrastructure.reading.queries.ereader_prereading_query import EreaderPrereadingQuery
from src.models import Book, Chapter, ChapterPrereadingContent, User
from tests.conftest import create_test_book
from tests.unit.infrastructure.conftest import AddChapter

DEFAULT_USER_ID = 1
CLIENT_BOOK_ID = "koreader-book-1"


@pytest.fixture
def query(db_session: AsyncSession) -> EreaderPrereadingQuery:
    """The query service wired the way the container wires it."""
    return EreaderPrereadingQuery(db=db_session)


@pytest.fixture
async def synced_book(db_session: AsyncSession) -> Book:
    """A book the device knows by its client id."""
    return await create_test_book(
        db_session=db_session,
        user_id=DEFAULT_USER_ID,
        title="Synced Book",
        client_book_id=CLIENT_BOOK_ID,
    )


async def add_prereading(
    db_session: AsyncSession, chapter: Chapter, summary: str = "A summary"
) -> ChapterPrereadingContent:
    """Generate prereading for a chapter."""
    content = ChapterPrereadingContent(
        chapter_id=chapter.id,
        summary=summary,
        keypoints=["first point", "second point"],
        questions=[
            {"question": "What is it?", "answer": "This.", "user_answer": "Mine."},
            {"question": "Why?", "answer": "Because.", "user_answer": ""},
        ],
        generated_at=datetime(2024, 5, 1, tzinfo=UTC),
        ai_model="test-model",
    )
    db_session.add(content)
    await db_session.commit()
    await db_session.refresh(content)
    return content


async def test_unknown_client_book_is_distinguished_from_one_without_prereading(
    query: EreaderPrereadingQuery, synced_book: Book, add_chapter: AddChapter
) -> None:
    await add_chapter(synced_book, "No prereading", chapter_number=1)

    assert await query.list_for_client_book(CLIENT_BOOK_ID, UserId(DEFAULT_USER_ID)) == ()
    assert await query.list_for_client_book("unknown", UserId(DEFAULT_USER_ID)) is None


async def test_another_users_book_is_invisible(
    query: EreaderPrereadingQuery,
    db_session: AsyncSession,
    synced_book: Book,
    add_chapter: AddChapter,
    other_user: User,
) -> None:
    chapter = await add_chapter(synced_book, "One", chapter_number=1)
    await add_prereading(db_session, chapter)

    assert await query.list_for_client_book(CLIENT_BOOK_ID, UserId(other_user.id)) is None


async def test_only_chapters_with_prereading_are_listed_in_chapter_order(
    query: EreaderPrereadingQuery,
    db_session: AsyncSession,
    synced_book: Book,
    add_chapter: AddChapter,
) -> None:
    third = await add_chapter(synced_book, "Third", chapter_number=3)
    first = await add_chapter(synced_book, "First", chapter_number=1)
    await add_chapter(synced_book, "Second", chapter_number=2)
    await add_prereading(db_session, third)
    await add_prereading(db_session, first)

    items = await query.list_for_client_book(CLIENT_BOOK_ID, UserId(DEFAULT_USER_ID))

    assert items is not None
    assert [item.chapter_name for item in items] == ["First", "Third"]


async def test_only_question_text_is_exposed_alongside_summary_and_keypoints(
    query: EreaderPrereadingQuery,
    db_session: AsyncSession,
    synced_book: Book,
    add_chapter: AddChapter,
) -> None:
    chapter = await add_chapter(synced_book, "One", chapter_number=1)
    content = await add_prereading(db_session, chapter, summary="What this chapter covers")

    items = await query.list_for_client_book(CLIENT_BOOK_ID, UserId(DEFAULT_USER_ID))

    assert items is not None
    item = items[0]
    assert item.chapter_id == chapter.id
    assert item.chapter_number == 1
    assert item.summary == "What this chapter covers"
    assert item.keypoints == ("first point", "second point")
    assert item.questions == ("What is it?", "Why?")
    assert item.generated_at == content.generated_at


async def test_a_nested_chapter_carries_its_parents_name(
    query: EreaderPrereadingQuery,
    db_session: AsyncSession,
    synced_book: Book,
    add_chapter: AddChapter,
) -> None:
    part = await add_chapter(synced_book, "Part One", chapter_number=1)
    nested = await add_chapter(synced_book, "Chapter 1.1", chapter_number=2, parent_id=part.id)
    await add_prereading(db_session, nested)

    items = await query.list_for_client_book(CLIENT_BOOK_ID, UserId(DEFAULT_USER_ID))

    assert items is not None
    assert items[0].parent_chapter_name == "Part One"


async def test_a_top_level_chapter_has_no_parent_name(
    query: EreaderPrereadingQuery,
    db_session: AsyncSession,
    synced_book: Book,
    add_chapter: AddChapter,
) -> None:
    chapter = await add_chapter(synced_book, "One", chapter_number=1)
    await add_prereading(db_session, chapter)

    items = await query.list_for_client_book(CLIENT_BOOK_ID, UserId(DEFAULT_USER_ID))

    assert items is not None
    assert items[0].parent_chapter_name is None


async def test_prereading_of_another_book_is_excluded(
    query: EreaderPrereadingQuery,
    db_session: AsyncSession,
    synced_book: Book,
    add_chapter: AddChapter,
) -> None:
    other_book = await create_test_book(
        db_session=db_session,
        user_id=DEFAULT_USER_ID,
        title="Other Book",
        client_book_id="koreader-book-2",
    )
    mine = await add_chapter(synced_book, "Mine", chapter_number=1)
    theirs = await add_chapter(other_book, "Theirs", chapter_number=1)
    await add_prereading(db_session, mine)
    await add_prereading(db_session, theirs)

    items = await query.list_for_client_book(CLIENT_BOOK_ID, UserId(DEFAULT_USER_ID))

    assert items is not None
    assert [item.chapter_name for item in items] == ["Mine"]
