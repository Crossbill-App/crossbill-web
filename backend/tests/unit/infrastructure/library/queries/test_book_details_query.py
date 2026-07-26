"""Tests for the book-details read model."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.reading.services.label_resolution_service import LabelResolutionService
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.reading.services.highlight_style_resolver import HighlightStyleResolver
from src.infrastructure.library.queries.book_details_query import BookDetailsQuery
from src.infrastructure.reading.repositories.highlight_style_repository import (
    HighlightStyleRepository,
)
from src.models import Book, Chapter, Flashcard, Note, User
from tests.conftest import (
    create_test_book,
    create_test_highlight,
    create_test_highlight_style,
)

DEFAULT_USER_ID = 1


@pytest.fixture
def query(db_session: AsyncSession) -> BookDetailsQuery:
    """The query service wired the way the container wires it."""
    return BookDetailsQuery(
        db=db_session,
        label_resolution_service=LabelResolutionService(
            highlight_style_repository=HighlightStyleRepository(db_session),
            highlight_style_resolver=HighlightStyleResolver(),
        ),
    )


async def add_chapter(
    db_session: AsyncSession, book: Book, name: str, chapter_number: int | None = None
) -> Chapter:
    """Attach a chapter to a book."""
    chapter = Chapter(book_id=book.id, name=name, chapter_number=chapter_number)
    db_session.add(chapter)
    await db_session.commit()
    await db_session.refresh(chapter)
    return chapter


async def add_other_user(db_session: AsyncSession) -> User:
    """Create a second user to check ownership scoping."""
    other = User(id=2, email="other@test.com")
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)
    return other


async def test_chapters_without_highlights_still_appear(
    query: BookDetailsQuery, db_session: AsyncSession, test_book: Book
) -> None:
    first = await add_chapter(db_session, test_book, "With highlights", chapter_number=1)
    await add_chapter(db_session, test_book, "Empty", chapter_number=2)
    await create_test_highlight(
        db_session=db_session,
        book=test_book,
        user_id=DEFAULT_USER_ID,
        chapter_id=first.id,
        text="Kept",
        datetime_str="2024-01-15 14:30:22",
    )

    view = await query.get_book_details(BookId(test_book.id), UserId(DEFAULT_USER_ID))

    assert view is not None
    assert [(c.name, len(c.highlights)) for c in view.chapters] == [
        ("With highlights", 1),
        ("Empty", 0),
    ]


async def test_highlight_group_for_a_chapter_outside_the_book_is_appended(
    query: BookDetailsQuery, db_session: AsyncSession, test_book: Book
) -> None:
    """Groups whose chapter is not one of the book's chapters must not be dropped."""
    own = await add_chapter(db_session, test_book, "Own chapter", chapter_number=1)
    other_book = await create_test_book(
        db_session=db_session, user_id=DEFAULT_USER_ID, title="Other Book"
    )
    stray = await add_chapter(db_session, other_book, "Stray chapter", chapter_number=9)
    await create_test_highlight(
        db_session=db_session,
        book=test_book,
        user_id=DEFAULT_USER_ID,
        chapter_id=stray.id,
        text="Stray highlight",
        datetime_str="2024-01-15 14:30:22",
    )

    view = await query.get_book_details(BookId(test_book.id), UserId(DEFAULT_USER_ID))

    assert view is not None
    assert [c.id for c in view.chapters] == [own.id, stray.id]
    assert [h.text for h in view.chapters[1].highlights] == ["Stray highlight"]


async def test_soft_deleted_highlights_are_excluded(
    query: BookDetailsQuery, db_session: AsyncSession, test_book: Book
) -> None:
    chapter = await add_chapter(db_session, test_book, "Chapter", chapter_number=1)
    await create_test_highlight(
        db_session=db_session,
        book=test_book,
        user_id=DEFAULT_USER_ID,
        chapter_id=chapter.id,
        text="Active",
        datetime_str="2024-01-15 14:30:22",
    )
    await create_test_highlight(
        db_session=db_session,
        book=test_book,
        user_id=DEFAULT_USER_ID,
        chapter_id=chapter.id,
        text="Deleted",
        datetime_str="2024-01-15 15:00:00",
        deleted_at=datetime.now(UTC),
    )

    view = await query.get_book_details(BookId(test_book.id), UserId(DEFAULT_USER_ID))

    assert view is not None
    assert [h.text for h in view.chapters[0].highlights] == ["Active"]


async def test_book_flashcards_exclude_highlight_cards(
    query: BookDetailsQuery, db_session: AsyncSession, test_book: Book
) -> None:
    chapter = await add_chapter(db_session, test_book, "Chapter", chapter_number=1)
    highlight = await create_test_highlight(
        db_session=db_session,
        book=test_book,
        user_id=DEFAULT_USER_ID,
        chapter_id=chapter.id,
        text="Highlighted",
        datetime_str="2024-01-15 14:30:22",
    )
    db_session.add_all(
        [
            Flashcard(
                user_id=DEFAULT_USER_ID,
                book_id=test_book.id,
                question="Book level?",
                answer="Yes",
            ),
            Flashcard(
                user_id=DEFAULT_USER_ID,
                book_id=test_book.id,
                chapter_id=chapter.id,
                question="Chapter level?",
                answer="Also yes",
            ),
            Flashcard(
                user_id=DEFAULT_USER_ID,
                book_id=test_book.id,
                highlight_id=highlight.id,
                question="Highlight level?",
                answer="No",
            ),
        ]
    )
    await db_session.commit()

    view = await query.get_book_details(BookId(test_book.id), UserId(DEFAULT_USER_ID))

    assert view is not None
    assert {card.question for card in view.book_flashcards} == {"Book level?", "Chapter level?"}
    assert [card.question for card in view.chapters[0].highlights[0].flashcards] == [
        "Highlight level?"
    ]


async def test_book_flashcards_carry_the_note_they_came_from(
    query: BookDetailsQuery, db_session: AsyncSession, test_book: Book
) -> None:
    # Callers use note_id to tell a note's card apart from a plain book card;
    # dropping it here is invisible until a cache goes stale somewhere else.
    note = Note(user_id=DEFAULT_USER_ID, title="Raskolnikov", body="")
    note.books = [test_book]
    db_session.add(note)
    await db_session.commit()
    await db_session.refresh(note)
    db_session.add_all(
        [
            Flashcard(
                user_id=DEFAULT_USER_ID,
                book_id=test_book.id,
                note_id=note.id,
                question="From a note?",
                answer="Yes",
            ),
            Flashcard(
                user_id=DEFAULT_USER_ID,
                book_id=test_book.id,
                question="From the book?",
                answer="Yes",
            ),
        ]
    )
    await db_session.commit()

    view = await query.get_book_details(BookId(test_book.id), UserId(DEFAULT_USER_ID))

    assert view is not None
    assert {(card.question, card.note_id) for card in view.book_flashcards} == {
        ("From a note?", note.id),
        ("From the book?", None),
    }


async def test_another_users_book_is_invisible(
    query: BookDetailsQuery, db_session: AsyncSession, test_book: Book
) -> None:
    other = await add_other_user(db_session)

    assert await query.get_book_details(BookId(test_book.id), UserId(other.id)) is None


async def test_another_users_highlights_are_invisible(
    query: BookDetailsQuery, db_session: AsyncSession, test_book: Book
) -> None:
    """A book is scoped to its owner, but highlight rows carry their own user_id."""
    other = await add_other_user(db_session)
    chapter = await add_chapter(db_session, test_book, "Chapter", chapter_number=1)
    await create_test_highlight(
        db_session=db_session,
        book=test_book,
        user_id=other.id,
        chapter_id=chapter.id,
        text="Not mine",
        datetime_str="2024-01-15 14:30:22",
    )

    view = await query.get_book_details(BookId(test_book.id), UserId(DEFAULT_USER_ID))

    assert view is not None
    assert view.chapters[0].highlights == ()


async def test_labels_come_from_the_label_resolution_service(
    query: BookDetailsQuery, db_session: AsyncSession, test_book: Book
) -> None:
    """The rule-derived label is resolved by the shared service, not re-encoded in SQL."""
    style = await create_test_highlight_style(
        db_session=db_session,
        user_id=DEFAULT_USER_ID,
        book_id=test_book.id,
        device_color="yellow",
        device_style="lighten",
        label="Key idea",
        ui_color="#ffcc00",
    )
    chapter = await add_chapter(db_session, test_book, "Chapter", chapter_number=1)
    await create_test_highlight(
        db_session=db_session,
        book=test_book,
        user_id=DEFAULT_USER_ID,
        chapter_id=chapter.id,
        text="Labelled",
        datetime_str="2024-01-15 14:30:22",
        highlight_style_id=style.id,
    )

    view = await query.get_book_details(BookId(test_book.id), UserId(DEFAULT_USER_ID))

    assert view is not None
    label = view.chapters[0].highlights[0].label
    assert label is not None
    assert (label.highlight_style_id, label.text, label.ui_color) == (
        style.id,
        "Key idea",
        "#ffcc00",
    )
