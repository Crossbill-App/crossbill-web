"""Tests for the note read model."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.common.value_objects.ids import (
    BookId,
    ChapterId,
    HighlightId,
    NoteId,
    TagId,
    UserId,
)
from src.domain.notes.entities.note import NoteKind
from src.infrastructure.notes.queries.note_query import NoteQuery
from src.models import Book, Chapter, Flashcard, Highlight, Note, Tag, User
from tests.conftest import create_test_book, create_test_highlight

DEFAULT_USER_ID = 1
OTHER_USER_ID = 2

AddNote = Callable[..., Awaitable[Note]]


@pytest.fixture
def query(db_session: AsyncSession) -> NoteQuery:
    """The query service wired the way the container wires it."""
    return NoteQuery(db=db_session)


@pytest.fixture
async def other_user(db_session: AsyncSession) -> User:
    """A second user, to check ownership scoping."""
    user = User(id=OTHER_USER_ID, email="other@test.com")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def add_note(db_session: AsyncSession) -> AddNote:
    """Persist a note with its association rows."""

    async def _add_note(
        book: Book,
        title: str = "A note",
        user_id: int = DEFAULT_USER_ID,
        body: str = "",
        kind: NoteKind | None = None,
        chapters: list[Chapter] | None = None,
        highlights: list[Highlight] | None = None,
        tags: list[Tag] | None = None,
    ) -> Note:
        note = Note(
            user_id=user_id,
            title=title,
            body=body,
            kind=kind.value if kind else None,
        )
        note.books = [book]
        note.chapters = list(chapters or [])
        note.highlights = list(highlights or [])
        note.tags = list(tags or [])
        db_session.add(note)
        await db_session.commit()
        await db_session.refresh(note)
        return note

    return _add_note


async def add_chapter(db_session: AsyncSession, book: Book, name: str) -> Chapter:
    """Attach a chapter to a book."""
    chapter = Chapter(book_id=book.id, name=name)
    db_session.add(chapter)
    await db_session.commit()
    await db_session.refresh(chapter)
    return chapter


async def add_tag(db_session: AsyncSession, book: Book, name: str, user_id: int) -> Tag:
    """Attach a tag to a book."""
    tag = Tag(book_id=book.id, user_id=user_id, name=name)
    db_session.add(tag)
    await db_session.commit()
    await db_session.refresh(tag)
    return tag


async def add_flashcard(
    db_session: AsyncSession,
    book: Book,
    note_id: int | None,
    question: str,
    user_id: int = DEFAULT_USER_ID,
) -> Flashcard:
    """Attach a flashcard to a note (or to the book alone)."""
    flashcard = Flashcard(
        user_id=user_id,
        book_id=book.id,
        note_id=note_id,
        question=question,
        answer="An answer",
    )
    db_session.add(flashcard)
    await db_session.commit()
    await db_session.refresh(flashcard)
    return flashcard


class TestGetNote:
    async def test_returns_the_note_with_its_links(
        self,
        query: NoteQuery,
        db_session: AsyncSession,
        test_book: Book,
        test_chapter: Chapter,
        test_highlight: Highlight,
        test_tag: Tag,
        add_note: AddNote,
    ) -> None:
        note = await add_note(
            test_book,
            title="Raskolnikov",
            body="Main character",
            kind=NoteKind.CHARACTER,
            chapters=[test_chapter],
            highlights=[test_highlight],
            tags=[test_tag],
        )

        view = await query.get_note(NoteId(note.id), UserId(DEFAULT_USER_ID))

        assert view is not None
        assert (view.title, view.body, view.kind) == (
            "Raskolnikov",
            "Main character",
            NoteKind.CHARACTER,
        )
        assert view.book_ids == (test_book.id,)
        assert [c.name for c in view.chapters] == [test_chapter.name]
        assert [h.text for h in view.highlights] == [test_highlight.text]
        assert [t.name for t in view.tags] == [test_tag.name]

    async def test_note_without_links_has_empty_collections(
        self, query: NoteQuery, test_book: Book, add_note: AddNote
    ) -> None:
        note = await add_note(test_book)

        view = await query.get_note(NoteId(note.id), UserId(DEFAULT_USER_ID))

        assert view is not None
        assert view.chapters == ()
        assert view.highlights == ()
        assert view.tags == ()
        assert view.flashcards == ()

    async def test_another_users_note_is_invisible(
        self, query: NoteQuery, test_book: Book, add_note: AddNote, other_user: User
    ) -> None:
        note = await add_note(test_book, user_id=OTHER_USER_ID)

        assert await query.get_note(NoteId(note.id), UserId(DEFAULT_USER_ID)) is None

    async def test_missing_note_returns_none(self, query: NoteQuery) -> None:
        assert await query.get_note(NoteId(9999), UserId(DEFAULT_USER_ID)) is None

    async def test_soft_deleted_highlight_keeps_its_id_but_is_not_rendered(
        self,
        query: NoteQuery,
        db_session: AsyncSession,
        test_book: Book,
        add_note: AddNote,
    ) -> None:
        live = await create_test_highlight(
            db_session=db_session,
            book=test_book,
            user_id=DEFAULT_USER_ID,
            text="Kept",
            datetime_str="2024-01-15 14:30:22",
        )
        deleted = await create_test_highlight(
            db_session=db_session,
            book=test_book,
            user_id=DEFAULT_USER_ID,
            text="Gone",
            datetime_str="2024-01-15 14:30:23",
            deleted_at=datetime.now(UTC),
        )
        note = await add_note(test_book, highlights=[live, deleted])

        view = await query.get_note(NoteId(note.id), UserId(DEFAULT_USER_ID))

        assert view is not None
        assert view.highlight_ids == (live.id, deleted.id)
        assert [h.text for h in view.highlights] == ["Kept"]

    async def test_links_owned_by_another_user_keep_their_id_but_are_not_rendered(
        self,
        query: NoteQuery,
        db_session: AsyncSession,
        test_book: Book,
        add_note: AddNote,
        other_user: User,
    ) -> None:
        # A note may point at rows the viewer does not own; the API reports the
        # ids verbatim but must not leak the rows themselves.
        other_book = await create_test_book(
            db_session=db_session, user_id=OTHER_USER_ID, title="Theirs"
        )
        other_chapter = await add_chapter(db_session, other_book, "Their chapter")
        other_highlight = await create_test_highlight(
            db_session=db_session,
            book=other_book,
            user_id=OTHER_USER_ID,
            text="Their highlight",
            datetime_str="2024-01-15 14:30:22",
        )
        other_tag = await add_tag(db_session, other_book, "Their tag", user_id=OTHER_USER_ID)
        note = await add_note(
            test_book,
            chapters=[other_chapter],
            highlights=[other_highlight],
            tags=[other_tag],
        )

        view = await query.get_note(NoteId(note.id), UserId(DEFAULT_USER_ID))

        assert view is not None
        assert (view.chapter_ids, view.highlight_ids, view.tag_ids) == (
            (other_chapter.id,),
            (other_highlight.id,),
            (other_tag.id,),
        )
        assert (view.chapters, view.highlights, view.tags) == ((), (), ())

    async def test_a_tag_with_no_highlights_is_still_shown(
        self, query: NoteQuery, db_session: AsyncSession, test_book: Book, add_note: AddNote
    ) -> None:
        # Tags are resolved by id, not by book: a book's tag listing only counts
        # tags in active highlight use, which would drop this one.
        tag = await add_tag(db_session, test_book, "Unused elsewhere", user_id=DEFAULT_USER_ID)
        note = await add_note(test_book, tags=[tag])

        view = await query.get_note(NoteId(note.id), UserId(DEFAULT_USER_ID))

        assert view is not None
        assert [t.name for t in view.tags] == ["Unused elsewhere"]

    async def test_returns_the_notes_own_flashcards_newest_first(
        self, query: NoteQuery, db_session: AsyncSession, test_book: Book, add_note: AddNote
    ) -> None:
        note = await add_note(test_book)
        other_note = await add_note(test_book, title="Other")
        older = await add_flashcard(db_session, test_book, note.id, "Older")
        newer = await add_flashcard(db_session, test_book, note.id, "Newer")
        newer.created_at = datetime(2030, 1, 1, tzinfo=UTC)
        await add_flashcard(db_session, test_book, other_note.id, "Someone else's note")
        await add_flashcard(db_session, test_book, None, "Book-level")
        await db_session.commit()

        view = await query.get_note(NoteId(note.id), UserId(DEFAULT_USER_ID))

        assert view is not None
        assert [f.question for f in view.flashcards] == ["Newer", "Older"]
        assert [f.id for f in view.flashcards] == [newer.id, older.id]
        assert view.flashcards[0].note_id == note.id

    async def test_another_users_flashcard_on_the_note_is_invisible(
        self,
        query: NoteQuery,
        db_session: AsyncSession,
        test_book: Book,
        add_note: AddNote,
        other_user: User,
    ) -> None:
        note = await add_note(test_book)
        await add_flashcard(db_session, test_book, note.id, "Theirs", user_id=OTHER_USER_ID)

        view = await query.get_note(NoteId(note.id), UserId(DEFAULT_USER_ID))

        assert view is not None
        assert view.flashcards == ()


class TestListForBook:
    async def test_orders_by_title_case_insensitively(
        self, query: NoteQuery, test_book: Book, add_note: AddNote
    ) -> None:
        for title in ("banana", "Apple", "cherry"):
            await add_note(test_book, title=title)

        views = await query.list_for_book(BookId(test_book.id), UserId(DEFAULT_USER_ID))

        assert [v.title for v in views] == ["Apple", "banana", "cherry"]

    async def test_excludes_notes_of_other_books_and_other_users(
        self,
        query: NoteQuery,
        db_session: AsyncSession,
        test_book: Book,
        add_note: AddNote,
        other_user: User,
    ) -> None:
        await add_note(test_book, title="Mine")
        await add_note(test_book, title="Theirs", user_id=OTHER_USER_ID)
        another_book = await create_test_book(
            db_session=db_session, user_id=DEFAULT_USER_ID, title="Another"
        )
        await add_note(another_book, title="Other book")

        views = await query.list_for_book(BookId(test_book.id), UserId(DEFAULT_USER_ID))

        assert [v.title for v in views] == ["Mine"]

    async def test_leaves_flashcards_empty(
        self, query: NoteQuery, db_session: AsyncSession, test_book: Book, add_note: AddNote
    ) -> None:
        note = await add_note(test_book)
        await add_flashcard(db_session, test_book, note.id, "Not in the list view")

        (view,) = await query.list_for_book(BookId(test_book.id), UserId(DEFAULT_USER_ID))

        assert view.flashcards == ()

    async def test_filters_by_kind(
        self, query: NoteQuery, test_book: Book, add_note: AddNote
    ) -> None:
        await add_note(test_book, title="A character", kind=NoteKind.CHARACTER)
        await add_note(test_book, title="A term", kind=NoteKind.TERM)

        views = await query.list_for_book(
            BookId(test_book.id), UserId(DEFAULT_USER_ID), kind=NoteKind.CHARACTER
        )

        assert [v.title for v in views] == ["A character"]

    async def test_filters_by_chapter(
        self,
        query: NoteQuery,
        db_session: AsyncSession,
        test_book: Book,
        test_chapter: Chapter,
        add_note: AddNote,
    ) -> None:
        other_chapter = await add_chapter(db_session, test_book, "Elsewhere")
        await add_note(test_book, title="Linked", chapters=[test_chapter])
        await add_note(test_book, title="Unlinked", chapters=[other_chapter])

        views = await query.list_for_book(
            BookId(test_book.id), UserId(DEFAULT_USER_ID), chapter_id=ChapterId(test_chapter.id)
        )

        assert [v.title for v in views] == ["Linked"]

    async def test_filters_by_highlight(
        self,
        query: NoteQuery,
        test_book: Book,
        test_highlight: Highlight,
        add_note: AddNote,
    ) -> None:
        await add_note(test_book, title="Linked", highlights=[test_highlight])
        await add_note(test_book, title="Unlinked")

        views = await query.list_for_book(
            BookId(test_book.id),
            UserId(DEFAULT_USER_ID),
            highlight_id=HighlightId(test_highlight.id),
        )

        assert [v.title for v in views] == ["Linked"]

    async def test_filters_by_tag(
        self, query: NoteQuery, test_book: Book, test_tag: Tag, add_note: AddNote
    ) -> None:
        await add_note(test_book, title="Linked", tags=[test_tag])
        await add_note(test_book, title="Unlinked")

        views = await query.list_for_book(
            BookId(test_book.id), UserId(DEFAULT_USER_ID), tag_id=TagId(test_tag.id)
        )

        assert [v.title for v in views] == ["Linked"]

    async def test_resolves_links_for_every_note_in_the_list(
        self,
        query: NoteQuery,
        db_session: AsyncSession,
        test_book: Book,
        test_chapter: Chapter,
        add_note: AddNote,
    ) -> None:
        second_chapter = await add_chapter(db_session, test_book, "Second")
        await add_note(test_book, title="First", chapters=[test_chapter])
        await add_note(test_book, title="Second", chapters=[second_chapter])

        views = await query.list_for_book(BookId(test_book.id), UserId(DEFAULT_USER_ID))

        assert [[c.name for c in v.chapters] for v in views] == [
            [test_chapter.name],
            ["Second"],
        ]

    async def test_no_notes_yields_an_empty_result(self, query: NoteQuery, test_book: Book) -> None:
        assert await query.list_for_book(BookId(test_book.id), UserId(DEFAULT_USER_ID)) == ()
