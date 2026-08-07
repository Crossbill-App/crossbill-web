"""DB-backed tests for SearchHydrationQuery: hits in, renderable items out."""

import hashlib
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.semantic.content_type import ContentType
from src.application.semantic.queries.semantic_search import SemanticSearchHit
from src.infrastructure.notes.orm.associations import note_books
from src.infrastructure.semantic.queries.search_hydration_query import SearchHydrationQuery
from src.models import Book, Chapter, ChapterDigest, Highlight, Note, User

USER_ID = 1
OTHER_USER_ID = 2


def _hit(content_type: ContentType, content_id: int, score: float) -> SemanticSearchHit:
    return SemanticSearchHit(
        content_type=content_type, content_id=content_id, book_id=None, score=score
    )


@pytest.fixture
async def users(db_session: AsyncSession) -> None:
    # db_session already seeds User(id=1); only the stranger needs adding here.
    db_session.add(User(id=OTHER_USER_ID, email="stranger@test.com"))
    await db_session.commit()


@pytest.fixture
async def book(db_session: AsyncSession, users: None) -> Book:
    row = Book(user_id=USER_ID, title="The Book")
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row


@pytest.fixture
def query(db_session: AsyncSession) -> SearchHydrationQuery:
    return SearchHydrationQuery(db_session)


async def _add_highlight(
    db: AsyncSession,
    book: Book,
    text: str,
    *,
    chapter_id: int | None = None,
    deleted: bool = False,
    user_id: int = USER_ID,
) -> Highlight:
    row = Highlight(
        user_id=user_id,
        book_id=book.id,
        chapter_id=chapter_id,
        text=text,
        page=42,
        datetime="2024-01-15 14:30:22",
        # Derived from text, not a fixed literal: (user_id, book_id, content_hash)
        # is a real unique constraint, and two highlights on the same book collide
        # on a shared placeholder.
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        deleted_at=datetime.now(UTC) if deleted else None,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def _add_chapter(db: AsyncSession, book: Book, name: str, number: int | None) -> Chapter:
    row = Chapter(book_id=book.id, name=name, chapter_number=number)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def _add_digest(db: AsyncSession, chapter: Chapter) -> ChapterDigest:
    row = ChapterDigest(
        chapter_id=chapter.id,
        summary="What happened",
        keypoints=["first", "second"],
        questions=[],
        generated_at=datetime.now(UTC),
        ai_model="test",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def _add_note(
    db: AsyncSession,
    title: str,
    *,
    books: tuple[Book, ...] = (),
    user_id: int = USER_ID,
) -> Note:
    row = Note(user_id=user_id, title=title, body="the body", kind="concept")
    db.add(row)
    await db.commit()
    await db.refresh(row)
    for linked in books:
        await db.execute(note_books.insert().values(note_id=row.id, book_id=linked.id))
    await db.commit()
    return row


class TestHighlights:
    async def test_maps_every_rendered_field(
        self, query: SearchHydrationQuery, db_session: AsyncSession, book: Book
    ) -> None:
        chapter = await _add_chapter(db_session, book, "Chapter Three", 3)
        highlight = await _add_highlight(db_session, book, "the text", chapter_id=chapter.id)

        views = await query.highlights([_hit(ContentType.HIGHLIGHT, highlight.id, 0.9)], USER_ID)

        assert len(views) == 1
        view = views[0]
        assert view.id == highlight.id
        assert view.score == 0.9
        assert view.book_id == book.id
        assert view.book_title == "The Book"
        assert view.chapter_id == chapter.id
        assert view.chapter_name == "Chapter Three"
        assert view.chapter_number == 3
        assert view.text == "the text"
        assert view.page == 42
        assert view.datetime == "2024-01-15 14:30:22"

    async def test_keeps_ranking_order(
        self, query: SearchHydrationQuery, db_session: AsyncSession, book: Book
    ) -> None:
        """Order comes from the hits, not from the id order the IN clause returns."""
        first = await _add_highlight(db_session, book, "first")
        second = await _add_highlight(db_session, book, "second")

        views = await query.highlights(
            [
                _hit(ContentType.HIGHLIGHT, second.id, 0.9),
                _hit(ContentType.HIGHLIGHT, first.id, 0.5),
            ],
            USER_ID,
        )

        assert [view.id for view in views] == [second.id, first.id]

    async def test_drops_a_soft_deleted_highlight(
        self, query: SearchHydrationQuery, db_session: AsyncSession, book: Book
    ) -> None:
        gone = await _add_highlight(db_session, book, "gone", deleted=True)
        kept = await _add_highlight(db_session, book, "kept")

        views = await query.highlights(
            [_hit(ContentType.HIGHLIGHT, gone.id, 0.9), _hit(ContentType.HIGHLIGHT, kept.id, 0.5)],
            USER_ID,
        )

        assert [view.id for view in views] == [kept.id]

    async def test_drops_another_users_highlight(
        self, query: SearchHydrationQuery, db_session: AsyncSession, book: Book
    ) -> None:
        theirs = await _add_highlight(db_session, book, "theirs", user_id=OTHER_USER_ID)

        views = await query.highlights([_hit(ContentType.HIGHLIGHT, theirs.id, 0.9)], USER_ID)

        assert views == ()

    async def test_leaves_chapter_fields_null_when_unattached(
        self, query: SearchHydrationQuery, db_session: AsyncSession, book: Book
    ) -> None:
        highlight = await _add_highlight(db_session, book, "loose")

        views = await query.highlights([_hit(ContentType.HIGHLIGHT, highlight.id, 0.9)], USER_ID)

        assert (views[0].chapter_id, views[0].chapter_name, views[0].chapter_number) == (
            None,
            None,
            None,
        )


class TestNotes:
    async def test_maps_fields_and_every_linked_book(
        self, query: SearchHydrationQuery, db_session: AsyncSession, book: Book
    ) -> None:
        second_book = Book(user_id=USER_ID, title="Second")
        db_session.add(second_book)
        await db_session.commit()
        await db_session.refresh(second_book)
        note = await _add_note(db_session, "A Title", books=(book, second_book))

        views = await query.notes([_hit(ContentType.NOTE, note.id, 0.8)], USER_ID)

        assert len(views) == 1
        view = views[0]
        assert (view.id, view.score, view.title, view.body, view.kind) == (
            note.id,
            0.8,
            "A Title",
            "the body",
            "concept",
        )
        assert {(ref.id, ref.title) for ref in view.books} == {
            (book.id, "The Book"),
            (second_book.id, "Second"),
        }

    async def test_returns_no_books_for_an_unlinked_note(
        self, query: SearchHydrationQuery, db_session: AsyncSession, users: None
    ) -> None:
        note = await _add_note(db_session, "Floating")

        views = await query.notes([_hit(ContentType.NOTE, note.id, 0.8)], USER_ID)

        assert views[0].books == ()

    async def test_drops_another_users_note(
        self, query: SearchHydrationQuery, db_session: AsyncSession, users: None
    ) -> None:
        theirs = await _add_note(db_session, "Theirs", user_id=OTHER_USER_ID)

        views = await query.notes([_hit(ContentType.NOTE, theirs.id, 0.8)], USER_ID)

        assert views == ()


class TestDigests:
    async def test_maps_chapter_and_book_context(
        self, query: SearchHydrationQuery, db_session: AsyncSession, book: Book
    ) -> None:
        # A spacer chapter keeps chapter.id from coincidentally matching digest.id:
        # both tables' autoincrement starts at 1 in a fresh test database, and the
        # test wants to prove the view carries two genuinely distinct ids.
        await _add_chapter(db_session, book, "Spacer", None)
        chapter = await _add_chapter(db_session, book, "Chapter One", 1)
        digest = await _add_digest(db_session, chapter)

        views = await query.digests([_hit(ContentType.DIGEST, digest.id, 0.7)], USER_ID)

        assert len(views) == 1
        view = views[0]
        assert view.id == digest.id
        assert view.chapter_id == chapter.id
        assert view.id != view.chapter_id
        assert view.chapter_name == "Chapter One"
        assert view.chapter_number == 1
        assert view.book_id == book.id
        assert view.book_title == "The Book"
        assert view.summary == "What happened"
        assert view.keypoints == ("first", "second")
        assert view.score == 0.7

    async def test_drops_another_users_digest(
        self, query: SearchHydrationQuery, db_session: AsyncSession, users: None
    ) -> None:
        their_book = Book(user_id=OTHER_USER_ID, title="Theirs")
        db_session.add(their_book)
        await db_session.commit()
        await db_session.refresh(their_book)
        chapter = await _add_chapter(db_session, their_book, "Theirs", 1)
        digest = await _add_digest(db_session, chapter)

        views = await query.digests([_hit(ContentType.DIGEST, digest.id, 0.7)], USER_ID)

        assert views == ()


class TestMissingSources:
    async def test_every_type_drops_a_hit_whose_row_is_gone(
        self, query: SearchHydrationQuery, users: None
    ) -> None:
        """The drop rule, not the FK cascade, is what keeps deleted content out.

        A hard-deleted note or digest normally takes its embedding with it, but
        the guarantee cannot rest on that having fired.
        """
        assert await query.highlights([_hit(ContentType.HIGHLIGHT, 999, 0.9)], USER_ID) == ()
        assert await query.notes([_hit(ContentType.NOTE, 999, 0.9)], USER_ID) == ()
        assert await query.digests([_hit(ContentType.DIGEST, 999, 0.9)], USER_ID) == ()


class TestEmptyInput:
    async def test_all_three_return_empty_without_querying(
        self, query: SearchHydrationQuery
    ) -> None:
        assert await query.highlights([], USER_ID) == ()
        assert await query.notes([], USER_ID) == ()
        assert await query.digests([], USER_ID) == ()
