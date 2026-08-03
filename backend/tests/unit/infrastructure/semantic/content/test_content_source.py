"""DB-backed tests for ContentSource (runs against in-memory SQLite)."""

import hashlib

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.semantic.content_type import ContentType
from src.config import get_settings
from src.infrastructure.semantic.content.content_source import ContentSource
from src.models import Book, Chapter, ChapterDigest, Embedding, Highlight, Note

USER_ID = 1


def _expected_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def _add_book(db: AsyncSession, title: str = "Book") -> Book:
    book = Book(user_id=USER_ID, title=title)
    db.add(book)
    await db.commit()
    await db.refresh(book)
    return book


async def _add_note(db: AsyncSession, title: str, body: str, books: list[Book]) -> Note:
    note = Note(user_id=USER_ID, title=title, body=body)
    note.books.extend(books)
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


async def _add_highlight(
    db: AsyncSession, book: Book, text: str, *, deleted: bool = False
) -> Highlight:
    from datetime import UTC, datetime  # noqa: PLC0415

    highlight = Highlight(
        user_id=USER_ID,
        book_id=book.id,
        text=text,
        datetime="2024-01-15 14:30:22",
        content_hash=_expected_hash(text)[:64],
        deleted_at=datetime.now(UTC) if deleted else None,
    )
    db.add(highlight)
    await db.commit()
    await db.refresh(highlight)
    return highlight


async def _add_digest(
    db: AsyncSession, book: Book, summary: str, keypoints: list[str]
) -> ChapterDigest:
    from datetime import UTC, datetime  # noqa: PLC0415

    chapter = Chapter(book_id=book.id, name="Chapter 1")
    db.add(chapter)
    await db.commit()
    await db.refresh(chapter)
    digest = ChapterDigest(
        chapter_id=chapter.id,
        summary=summary,
        keypoints=keypoints,
        questions=[],
        generated_at=datetime.now(UTC),
        ai_model="test",
    )
    db.add(digest)
    await db.commit()
    await db.refresh(digest)
    return digest


async def _add_embedding(db: AsyncSession, book: Book, content_id: int, content_hash: str) -> None:
    """Store a highlight embedding that is current for model bge-m3 @ version 1."""
    db.add(
        Embedding(
            user_id=USER_ID,
            content_type=ContentType.HIGHLIGHT.value,
            content_id=content_id,
            book_id=book.id,
            embedding=[0.1, 0.2],
            model_name="bge-m3",
            model_version="1",
            content_hash=content_hash,
        )
    )
    await db.commit()


@pytest.fixture
def content_source(db_session: AsyncSession) -> ContentSource:
    return ContentSource(db_session, get_settings())


class TestGetEmbeddable:
    async def test_note_resolves_text_hash_user_and_single_book(
        self, content_source: ContentSource, db_session: AsyncSession
    ) -> None:
        book = await _add_book(db_session)
        note = await _add_note(db_session, "Term", "Explanation", [book])

        emb = await content_source.get_embeddable(ContentType.NOTE, note.id)

        assert emb is not None
        assert emb.text == "Term\n\nExplanation"
        assert emb.content_hash == _expected_hash("Term\n\nExplanation")
        assert emb.user_id == USER_ID
        assert emb.book_id == book.id

    async def test_note_with_empty_body_is_title_only(
        self, content_source: ContentSource, db_session: AsyncSession
    ) -> None:
        note = await _add_note(db_session, "Bare title", "", [])

        emb = await content_source.get_embeddable(ContentType.NOTE, note.id)

        assert emb is not None
        assert emb.text == "Bare title"
        assert emb.book_id is None

    async def test_note_with_two_books_has_no_single_book(
        self, content_source: ContentSource, db_session: AsyncSession
    ) -> None:
        book_a = await _add_book(db_session, "A")
        book_b = await _add_book(db_session, "B")
        note = await _add_note(db_session, "T", "B", [book_a, book_b])

        emb = await content_source.get_embeddable(ContentType.NOTE, note.id)

        assert emb is not None
        assert emb.book_id is None

    async def test_highlight_resolves_text_user_and_book(
        self, content_source: ContentSource, db_session: AsyncSession
    ) -> None:
        book = await _add_book(db_session)
        highlight = await _add_highlight(db_session, book, "A memorable line")

        emb = await content_source.get_embeddable(ContentType.HIGHLIGHT, highlight.id)

        assert emb is not None
        assert emb.text == "A memorable line"
        assert emb.content_hash == _expected_hash("A memorable line")
        assert emb.user_id == USER_ID
        assert emb.book_id == book.id

    async def test_soft_deleted_highlight_returns_none(
        self, content_source: ContentSource, db_session: AsyncSession
    ) -> None:
        book = await _add_book(db_session)
        highlight = await _add_highlight(db_session, book, "gone", deleted=True)

        assert await content_source.get_embeddable(ContentType.HIGHLIGHT, highlight.id) is None

    async def test_digest_joins_summary_and_keypoints(
        self, content_source: ContentSource, db_session: AsyncSession
    ) -> None:
        book = await _add_book(db_session)
        digest = await _add_digest(db_session, book, "Summary", ["one", "two"])

        emb = await content_source.get_embeddable(ContentType.DIGEST, digest.id)

        assert emb is not None
        assert emb.text == "Summary\n\none\ntwo"
        assert emb.user_id == USER_ID
        assert emb.book_id == book.id

    async def test_missing_content_returns_none(self, content_source: ContentSource) -> None:
        assert await content_source.get_embeddable(ContentType.NOTE, 9999) is None


class TestIterWorkItems:
    async def test_returns_units_missing_an_embedding(
        self, content_source: ContentSource, db_session: AsyncSession
    ) -> None:
        book = await _add_book(db_session)
        note = await _add_note(db_session, "N", "body", [book])
        highlight = await _add_highlight(db_session, book, "text")
        digest = await _add_digest(db_session, book, "s", ["k"])

        items = await content_source.iter_work_items(USER_ID, None)

        by_type = {(item.content_type, item.content_id) for item in items}
        assert (ContentType.NOTE, note.id) in by_type
        assert (ContentType.HIGHLIGHT, highlight.id) in by_type
        assert (ContentType.DIGEST, digest.id) in by_type

    async def test_book_scope_excludes_other_books(
        self, content_source: ContentSource, db_session: AsyncSession
    ) -> None:
        book = await _add_book(db_session, "target")
        other = await _add_book(db_session, "other")
        highlight = await _add_highlight(db_session, book, "in scope")
        out = await _add_highlight(db_session, other, "out of scope")

        items = await content_source.iter_work_items(USER_ID, book.id)

        ids = {item.content_id for item in items if item.content_type == ContentType.HIGHLIGHT}
        assert highlight.id in ids
        assert out.id not in ids

    async def test_excludes_units_with_current_embedding(self, db_session: AsyncSession) -> None:
        configured = get_settings().model_copy(
            update={"EMBEDDING_MODEL_NAME": "bge-m3", "EMBEDDING_MODEL_VERSION": "1"}
        )
        source = ContentSource(db_session, configured)
        book = await _add_book(db_session)
        embedded = await _add_highlight(db_session, book, "already embedded")
        pending = await _add_highlight(db_session, book, "still pending")
        # The hash must match the highlight's own text, or the row is content-stale.
        await _add_embedding(db_session, book, embedded.id, _expected_hash("already embedded"))

        items = await source.iter_work_items(USER_ID, None)

        ids = {item.content_id for item in items if item.content_type == ContentType.HIGHLIGHT}
        assert pending.id in ids
        assert embedded.id not in ids

    async def test_includes_unit_whose_content_hash_drifted(self, db_session: AsyncSession) -> None:
        """ADR-0002: stale = content_hash mismatch OR model_version mismatch.

        The drift case — content edited while embeddings were off, or a job that
        exhausted its retries — leaves a row whose model matches but whose hash
        is from the previous text. Backfill is the only backstop for it.
        """
        configured = get_settings().model_copy(
            update={"EMBEDDING_MODEL_NAME": "bge-m3", "EMBEDDING_MODEL_VERSION": "1"}
        )
        source = ContentSource(db_session, configured)
        book = await _add_book(db_session)
        edited = await _add_highlight(db_session, book, "the edited text")
        await _add_embedding(db_session, book, edited.id, _expected_hash("the original text"))

        items = await source.iter_work_items(USER_ID, None)

        ids = {item.content_id for item in items if item.content_type == ContentType.HIGHLIGHT}
        assert edited.id in ids

    async def test_includes_orphaned_embedding_so_the_job_prunes_it(
        self, db_session: AsyncSession
    ) -> None:
        """An embedding outliving its source is handed back so the job deletes it."""
        configured = get_settings().model_copy(
            update={"EMBEDDING_MODEL_NAME": "bge-m3", "EMBEDDING_MODEL_VERSION": "1"}
        )
        source = ContentSource(db_session, configured)
        book = await _add_book(db_session)
        deleted = await _add_highlight(db_session, book, "since deleted", deleted=True)
        await _add_embedding(db_session, book, deleted.id, _expected_hash("since deleted"))

        items = await source.iter_work_items(USER_ID, None)

        ids = {item.content_id for item in items if item.content_type == ContentType.HIGHLIGHT}
        assert deleted.id in ids
        # And the job's own resolution step reports it as gone, so it gets deleted.
        assert await source.get_embeddable(ContentType.HIGHLIGHT, deleted.id) is None


class TestGetEmbeddableMany:
    async def test_resolves_a_batch_and_omits_dead_sources(
        self, content_source: ContentSource, db_session: AsyncSession
    ) -> None:
        book = await _add_book(db_session)
        alive = await _add_highlight(db_session, book, "still here")
        gone = await _add_highlight(db_session, book, "soft deleted", deleted=True)

        found = await content_source.get_embeddable_many(
            ContentType.HIGHLIGHT, [alive.id, gone.id, 9999]
        )

        assert set(found) == {alive.id}
        assert found[alive.id].text == "still here"
        assert found[alive.id].content_hash == _expected_hash("still here")

    async def test_batches_note_book_links_without_a_query_per_note(
        self, content_source: ContentSource, db_session: AsyncSession
    ) -> None:
        """Book scope must survive batching: one link query, grouped in memory."""
        one = await _add_book(db_session, "one")
        two = await _add_book(db_session, "two")
        single = await _add_note(db_session, "single", "body", [one])
        spanning = await _add_note(db_session, "spanning", "body", [one, two])
        unlinked = await _add_note(db_session, "unlinked", "body", [])

        found = await content_source.get_embeddable_many(
            ContentType.NOTE, [single.id, spanning.id, unlinked.id]
        )

        assert found[single.id].book_id == one.id
        assert found[spanning.id].book_id is None
        assert found[unlinked.id].book_id is None

    async def test_empty_input_touches_the_database_not_at_all(
        self, content_source: ContentSource
    ) -> None:
        assert await content_source.get_embeddable_many(ContentType.NOTE, []) == {}

    async def test_single_lookup_agrees_with_the_batch(
        self, content_source: ContentSource, db_session: AsyncSession
    ) -> None:
        """get_embeddable delegates to the batch path, so the two cannot drift."""
        book = await _add_book(db_session)
        digest = await _add_digest(db_session, book, "summary", ["a", "b"])

        one = await content_source.get_embeddable(ContentType.DIGEST, digest.id)
        many = await content_source.get_embeddable_many(ContentType.DIGEST, [digest.id])

        assert one is not None
        assert many[digest.id] == one
