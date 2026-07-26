"""Tests for the book-flashcards read model."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.reading.services.label_resolution_service import LabelResolutionService
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.reading.services.highlight_style_resolver import HighlightStyleResolver
from src.infrastructure.learning.queries.book_flashcard_query import BookFlashcardQuery
from src.infrastructure.reading.repositories.highlight_style_repository import (
    HighlightStyleRepository,
)
from src.models import Book, Chapter, Flashcard, Highlight, Note, Tag, User
from tests.conftest import (
    create_test_book,
    create_test_highlight,
    create_test_highlight_style,
)

DEFAULT_USER_ID = 1
OTHER_USER_ID = 2


@pytest.fixture
def query(db_session: AsyncSession) -> BookFlashcardQuery:
    """The query service wired the way the container wires it."""
    return BookFlashcardQuery(
        db=db_session,
        label_resolution_service=LabelResolutionService(
            highlight_style_repository=HighlightStyleRepository(db_session),
            highlight_style_resolver=HighlightStyleResolver(),
        ),
    )


@pytest.fixture
async def other_user(db_session: AsyncSession) -> User:
    """A second user, to check ownership scoping."""
    user = User(id=OTHER_USER_ID, email="other@test.com")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def add_flashcard(
    db_session: AsyncSession,
    book: Book,
    question: str = "Q",
    answer: str = "A",
    user_id: int = DEFAULT_USER_ID,
    highlight: Highlight | None = None,
    highlight_id: int | None = None,
    chapter_id: int | None = None,
    note_id: int | None = None,
    created_at: datetime | None = None,
) -> Flashcard:
    """Persist a flashcard, optionally pointing at a highlight."""
    flashcard = Flashcard(
        user_id=user_id,
        book_id=book.id,
        highlight_id=highlight.id if highlight else highlight_id,
        chapter_id=chapter_id,
        note_id=note_id,
        question=question,
        answer=answer,
    )
    if created_at is not None:
        flashcard.created_at = created_at
    db_session.add(flashcard)
    await db_session.commit()
    await db_session.refresh(flashcard)
    return flashcard


async def add_chapter(
    db_session: AsyncSession, book: Book, name: str, chapter_number: int | None = None
) -> Chapter:
    """Attach a chapter to a book."""
    chapter = Chapter(book_id=book.id, name=name, chapter_number=chapter_number)
    db_session.add(chapter)
    await db_session.commit()
    await db_session.refresh(chapter)
    return chapter


async def tag_highlight(
    db_session: AsyncSession, book: Book, highlight: Highlight, name: str
) -> Tag:
    """Attach a new tag to a highlight."""
    tag = Tag(book_id=book.id, user_id=highlight.user_id, name=name)
    db_session.add(tag)
    await db_session.commit()
    highlight.tags.append(tag)
    await db_session.commit()
    await db_session.refresh(tag)
    return tag


async def test_flashcards_come_back_newest_first(
    query: BookFlashcardQuery, db_session: AsyncSession, test_book: Book
) -> None:
    await add_flashcard(
        db_session,
        test_book,
        question="Older",
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    await add_flashcard(
        db_session,
        test_book,
        question="Newer",
        created_at=datetime(2024, 6, 1, tzinfo=UTC),
    )

    view = await query.list_for_book(BookId(test_book.id), UserId(DEFAULT_USER_ID))

    assert [card.question for card in view] == ["Newer", "Older"]


async def test_book_level_flashcard_has_no_highlight(
    query: BookFlashcardQuery, db_session: AsyncSession, test_book: Book
) -> None:
    chapter = await add_chapter(db_session, test_book, "Chapter", chapter_number=1)
    await add_flashcard(db_session, test_book, chapter_id=chapter.id)

    view = await query.list_for_book(BookId(test_book.id), UserId(DEFAULT_USER_ID))

    assert len(view) == 1
    assert view[0].highlight_id is None
    assert view[0].highlight is None
    assert view[0].note_id is None
    assert view[0].chapter_id == chapter.id


async def test_flashcard_made_from_a_note_carries_its_note_id(
    query: BookFlashcardQuery, db_session: AsyncSession, test_book: Book
) -> None:
    note = Note(user_id=DEFAULT_USER_ID, title="Raskolnikov", body="")
    note.books = [test_book]
    db_session.add(note)
    await db_session.commit()
    await db_session.refresh(note)
    await add_flashcard(db_session, test_book, note_id=note.id)

    view = await query.list_for_book(BookId(test_book.id), UserId(DEFAULT_USER_ID))

    assert view[0].note_id == note.id


async def test_highlight_carries_its_chapter_and_tags(
    query: BookFlashcardQuery,
    db_session: AsyncSession,
    test_book: Book,
) -> None:
    chapter = await add_chapter(db_session, test_book, "Crime", chapter_number=3)
    highlight = await create_test_highlight(
        db_session=db_session,
        book=test_book,
        user_id=DEFAULT_USER_ID,
        chapter_id=chapter.id,
        text="Highlighted text",
        page=42,
        datetime_str="2024-01-15 14:30:22",
    )
    tag = await tag_highlight(db_session, test_book, highlight, "Motif")
    await add_flashcard(db_session, test_book, highlight=highlight)

    view = await query.list_for_book(BookId(test_book.id), UserId(DEFAULT_USER_ID))

    embedded = view[0].highlight
    assert embedded is not None
    assert (embedded.id, embedded.text, embedded.page, embedded.datetime) == (
        highlight.id,
        "Highlighted text",
        42,
        "2024-01-15 14:30:22",
    )
    assert (embedded.chapter_id, embedded.chapter_name, embedded.chapter_number) == (
        chapter.id,
        "Crime",
        3,
    )
    assert [(t.id, t.name, t.tag_group_id) for t in embedded.tags] == [(tag.id, "Motif", None)]


async def test_label_comes_from_the_label_resolution_service(
    query: BookFlashcardQuery, db_session: AsyncSession, test_book: Book
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
    highlight = await create_test_highlight(
        db_session=db_session,
        book=test_book,
        user_id=DEFAULT_USER_ID,
        text="Labelled",
        datetime_str="2024-01-15 14:30:22",
        highlight_style_id=style.id,
    )
    await add_flashcard(db_session, test_book, highlight=highlight)

    view = await query.list_for_book(BookId(test_book.id), UserId(DEFAULT_USER_ID))

    embedded = view[0].highlight
    assert embedded is not None
    assert embedded.label is not None
    assert (embedded.label.highlight_style_id, embedded.label.text, embedded.label.ui_color) == (
        style.id,
        "Key idea",
        "#ffcc00",
    )


async def test_unstyled_highlight_has_no_label(
    query: BookFlashcardQuery, db_session: AsyncSession, test_book: Book
) -> None:
    highlight = await create_test_highlight(
        db_session=db_session,
        book=test_book,
        user_id=DEFAULT_USER_ID,
        text="Unstyled",
        datetime_str="2024-01-15 14:30:22",
    )
    await add_flashcard(db_session, test_book, highlight=highlight)

    view = await query.list_for_book(BookId(test_book.id), UserId(DEFAULT_USER_ID))

    embedded = view[0].highlight
    assert embedded is not None
    assert embedded.label is None


async def test_soft_deleted_highlight_keeps_its_id_but_is_not_rendered(
    query: BookFlashcardQuery, db_session: AsyncSession, test_book: Book
) -> None:
    highlight = await create_test_highlight(
        db_session=db_session,
        book=test_book,
        user_id=DEFAULT_USER_ID,
        text="Gone",
        datetime_str="2024-01-15 14:30:22",
        deleted_at=datetime.now(UTC),
    )
    await add_flashcard(db_session, test_book, highlight=highlight)

    view = await query.list_for_book(BookId(test_book.id), UserId(DEFAULT_USER_ID))

    assert view[0].highlight_id == highlight.id
    assert view[0].highlight is None


async def test_highlight_owned_by_another_user_is_not_rendered(
    query: BookFlashcardQuery,
    db_session: AsyncSession,
    test_book: Book,
    other_user: User,
) -> None:
    other_book = await create_test_book(
        db_session=db_session, user_id=other_user.id, title="Their book"
    )
    their_highlight = await create_test_highlight(
        db_session=db_session,
        book=other_book,
        user_id=other_user.id,
        text="Theirs",
        datetime_str="2024-01-15 14:30:22",
    )
    await add_flashcard(db_session, test_book, highlight_id=their_highlight.id)

    view = await query.list_for_book(BookId(test_book.id), UserId(DEFAULT_USER_ID))

    assert view[0].highlight_id == their_highlight.id
    assert view[0].highlight is None


async def test_another_users_flashcard_on_the_book_is_invisible(
    query: BookFlashcardQuery,
    db_session: AsyncSession,
    test_book: Book,
    other_user: User,
) -> None:
    await add_flashcard(db_session, test_book, question="Mine")
    await add_flashcard(db_session, test_book, question="Theirs", user_id=other_user.id)

    view = await query.list_for_book(BookId(test_book.id), UserId(DEFAULT_USER_ID))

    assert [card.question for card in view] == ["Mine"]


async def test_flashcards_of_another_book_are_excluded(
    query: BookFlashcardQuery, db_session: AsyncSession, test_book: Book
) -> None:
    other_book = await create_test_book(
        db_session=db_session, user_id=DEFAULT_USER_ID, title="Another book"
    )
    await add_flashcard(db_session, test_book, question="This book")
    await add_flashcard(db_session, other_book, question="Other book")

    view = await query.list_for_book(BookId(test_book.id), UserId(DEFAULT_USER_ID))

    assert [card.question for card in view] == ["This book"]


async def test_book_without_flashcards_yields_an_empty_result(
    query: BookFlashcardQuery, test_book: Book
) -> None:
    assert await query.list_for_book(BookId(test_book.id), UserId(DEFAULT_USER_ID)) == ()
