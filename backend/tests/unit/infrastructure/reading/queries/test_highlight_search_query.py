"""Tests for the in-book highlight-search read model."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.reading.services.label_resolution_service import LabelResolutionService
from src.domain.common.value_objects.ids import BookId, UserId
from src.infrastructure.reading.queries.highlight_search_query import HighlightSearchQuery
from src.models import Book, Flashcard, Highlight, Note, Tag, User
from tests.conftest import (
    create_test_book,
    create_test_highlight,
    create_test_highlight_style,
)
from tests.unit.infrastructure.conftest import AddChapter

DEFAULT_USER_ID = 1


@pytest.fixture
def query(
    db_session: AsyncSession, label_resolution_service: LabelResolutionService
) -> HighlightSearchQuery:
    """The query service wired the way the container wires it."""
    return HighlightSearchQuery(db=db_session, label_resolution_service=label_resolution_service)


async def add_highlight(
    db_session: AsyncSession,
    book: Book,
    text: str,
    datetime_str: str,
    chapter_id: int | None = None,
    page: int | None = None,
    deleted_at: datetime | None = None,
    highlight_style_id: int | None = None,
) -> Highlight:
    """A matchable highlight on the book, owned by the default user."""
    return await create_test_highlight(
        db_session=db_session,
        book=book,
        user_id=DEFAULT_USER_ID,
        text=text,
        datetime_str=datetime_str,
        chapter_id=chapter_id,
        page=page,
        deleted_at=deleted_at,
        highlight_style_id=highlight_style_id,
    )


async def test_missing_book_is_distinguished_from_a_book_with_no_matches(
    query: HighlightSearchQuery, test_book: Book
) -> None:
    empty = await query.search_in_book(BookId(test_book.id), UserId(DEFAULT_USER_ID), "nothing")
    assert empty is not None
    assert empty.chapters == ()
    assert empty.total == 0

    assert (
        await query.search_in_book(BookId(test_book.id + 999), UserId(DEFAULT_USER_ID), "x") is None
    )


async def test_another_users_book_is_invisible(
    query: HighlightSearchQuery, test_book: Book, other_user: User
) -> None:
    assert await query.search_in_book(BookId(test_book.id), UserId(other_user.id), "needle") is None


async def test_matches_are_grouped_by_chapter_in_chapter_number_order(
    query: HighlightSearchQuery, db_session: AsyncSession, test_book: Book, add_chapter: AddChapter
) -> None:
    second = await add_chapter(test_book, "Second", chapter_number=2)
    first = await add_chapter(test_book, "First", chapter_number=1)
    await add_highlight(
        db_session,
        test_book,
        "needle in chapter two",
        "2024-01-01 10:00:00",
        chapter_id=second.id,
        page=5,
    )
    await add_highlight(
        db_session,
        test_book,
        "needle in chapter one",
        "2024-01-02 10:00:00",
        chapter_id=first.id,
        page=1,
    )

    view = await query.search_in_book(BookId(test_book.id), UserId(DEFAULT_USER_ID), "needle")

    assert view is not None
    assert [chapter.name for chapter in view.chapters] == ["First", "Second"]
    assert view.total == 2


async def test_a_chapters_own_timestamps_are_reported(
    query: HighlightSearchQuery, db_session: AsyncSession, test_book: Book, add_chapter: AddChapter
) -> None:
    chapter = await add_chapter(test_book, "Renamed since", chapter_number=1)
    # A chapter that was created once and edited later must report both times,
    # not the creation time twice.
    chapter.created_at = datetime(2024, 1, 1, tzinfo=UTC)
    chapter.updated_at = datetime(2024, 6, 30, tzinfo=UTC)
    await db_session.commit()
    await add_highlight(
        db_session, test_book, "needle here", "2024-01-01 10:00:00", chapter_id=chapter.id
    )

    view = await query.search_in_book(BookId(test_book.id), UserId(DEFAULT_USER_ID), "needle")

    assert view is not None
    assert view.chapters[0].created_at == chapter.created_at
    assert view.chapters[0].updated_at == chapter.updated_at
    assert view.chapters[0].created_at != view.chapters[0].updated_at


async def test_highlights_within_a_chapter_are_ordered_by_page(
    query: HighlightSearchQuery, db_session: AsyncSession, test_book: Book, add_chapter: AddChapter
) -> None:
    chapter = await add_chapter(test_book, "Only", chapter_number=1)
    for page, text in ((9, "needle late"), (2, "needle early")):
        await add_highlight(
            db_session,
            test_book,
            text,
            f"2024-01-0{page % 8 + 1} 10:00:00",
            chapter_id=chapter.id,
            page=page,
        )

    view = await query.search_in_book(BookId(test_book.id), UserId(DEFAULT_USER_ID), "needle")

    assert view is not None
    assert [h.page for h in view.chapters[0].highlights] == [2, 9]


async def test_soft_deleted_and_chapterless_matches_are_excluded_from_rows_and_total(
    query: HighlightSearchQuery, db_session: AsyncSession, test_book: Book, add_chapter: AddChapter
) -> None:
    chapter = await add_chapter(test_book, "Only", chapter_number=1)
    await add_highlight(
        db_session, test_book, "needle kept", "2024-01-01 10:00:00", chapter_id=chapter.id
    )
    await add_highlight(
        db_session,
        test_book,
        "needle deleted",
        "2024-01-02 10:00:00",
        chapter_id=chapter.id,
        deleted_at=datetime.now(UTC),
    )
    await add_highlight(db_session, test_book, "needle without a chapter", "2024-01-03 10:00:00")

    view = await query.search_in_book(BookId(test_book.id), UserId(DEFAULT_USER_ID), "needle")

    assert view is not None
    assert [h.text for h in view.chapters[0].highlights] == ["needle kept"]
    assert view.total == 1


async def test_matches_in_another_book_are_excluded(
    query: HighlightSearchQuery, db_session: AsyncSession, test_book: Book, add_chapter: AddChapter
) -> None:
    other_book = await create_test_book(
        db_session=db_session, user_id=DEFAULT_USER_ID, title="Other Book"
    )
    chapter = await add_chapter(test_book, "Mine", chapter_number=1)
    other_chapter = await add_chapter(other_book, "Theirs", chapter_number=1)
    await add_highlight(
        db_session, test_book, "needle here", "2024-01-01 10:00:00", chapter_id=chapter.id
    )
    await add_highlight(
        db_session,
        other_book,
        "needle elsewhere",
        "2024-01-02 10:00:00",
        chapter_id=other_chapter.id,
    )

    view = await query.search_in_book(BookId(test_book.id), UserId(DEFAULT_USER_ID), "needle")

    assert view is not None
    assert [h.text for h in view.chapters[0].highlights] == ["needle here"]


async def test_tags_flashcards_and_the_resolved_label_ride_along(
    query: HighlightSearchQuery, db_session: AsyncSession, test_book: Book, add_chapter: AddChapter
) -> None:
    chapter = await add_chapter(test_book, "Only", chapter_number=1)
    style = await create_test_highlight_style(
        db_session=db_session,
        user_id=DEFAULT_USER_ID,
        book_id=test_book.id,
        label="Key idea",
        ui_color="#123456",
    )
    highlight = await add_highlight(
        db_session,
        test_book,
        "needle with context",
        "2024-01-01 10:00:00",
        chapter_id=chapter.id,
        highlight_style_id=style.id,
    )
    tag = Tag(book_id=test_book.id, user_id=DEFAULT_USER_ID, name="theme")
    db_session.add(tag)
    await db_session.commit()
    await db_session.refresh(tag)
    highlight.tags.append(tag)
    note = Note(user_id=DEFAULT_USER_ID, title="A note", body="Something worth keeping")
    db_session.add(note)
    await db_session.commit()
    await db_session.refresh(note)
    db_session.add(
        Flashcard(
            user_id=DEFAULT_USER_ID,
            book_id=test_book.id,
            highlight_id=highlight.id,
            note_id=note.id,
            question="Q?",
            answer="A.",
        )
    )
    await db_session.commit()

    view = await query.search_in_book(BookId(test_book.id), UserId(DEFAULT_USER_ID), "needle")

    assert view is not None
    match = view.chapters[0].highlights[0]
    assert match.chapter_name == "Only"
    assert match.chapter_number == 1
    assert [t.name for t in match.tags] == ["theme"]
    assert [card.question for card in match.flashcards] == ["Q?"]
    assert [card.note_id for card in match.flashcards] == [note.id]
    assert match.label is not None
    assert match.label.highlight_style_id == style.id
    assert match.label.text == "Key idea"
    assert match.label.ui_color == "#123456"


async def test_limit_caps_the_matches_before_grouping(
    query: HighlightSearchQuery, db_session: AsyncSession, test_book: Book, add_chapter: AddChapter
) -> None:
    chapter = await add_chapter(test_book, "Only", chapter_number=1)
    for index in range(3):
        await add_highlight(
            db_session,
            test_book,
            f"needle {index}",
            f"2024-01-0{index + 1} 10:00:00",
            chapter_id=chapter.id,
        )

    view = await query.search_in_book(
        BookId(test_book.id), UserId(DEFAULT_USER_ID), "needle", limit=2
    )

    assert view is not None
    assert view.total == 2


async def test_like_wildcards_in_the_search_text_are_escaped(
    query: HighlightSearchQuery, db_session: AsyncSession, test_book: Book, add_chapter: AddChapter
) -> None:
    chapter = await add_chapter(test_book, "Only", chapter_number=1)
    await add_highlight(
        db_session, test_book, "a literal 100% match", "2024-01-01 10:00:00", chapter_id=chapter.id
    )
    await add_highlight(
        db_session, test_book, "no percent sign here", "2024-01-02 10:00:00", chapter_id=chapter.id
    )

    view = await query.search_in_book(BookId(test_book.id), UserId(DEFAULT_USER_ID), "100%")

    assert view is not None
    assert view.total == 1
