"""Tests for books API endpoints."""

from datetime import UTC, datetime
from typing import NamedTuple
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src import models
from src.infrastructure.semantic.repositories.embedding_repository import EmbeddingRepository
from tests.conftest import create_test_book, create_test_highlight
from tests.semantic_helpers import index_highlight, plant_indexed_highlight

# Default user ID used by services (matches conftest default user)
DEFAULT_USER_ID = 1


class BookWithChapter(NamedTuple):
    book: models.Book
    chapter: models.Chapter


class BookWithHighlights(NamedTuple):
    book: models.Book
    highlights: list[models.Highlight]


class BookWithChapterAndHighlights(NamedTuple):
    book: models.Book
    chapter: models.Chapter
    highlights: list[models.Highlight]


@pytest.fixture
async def test_book_with_isbn(db_session: AsyncSession) -> models.Book:
    return await create_test_book(
        db_session=db_session,
        user_id=DEFAULT_USER_ID,
        title="Test Book",
        author="Test Author",
        isbn="1234567890",
    )


@pytest.fixture
async def book_with_chapter(db_session: AsyncSession) -> BookWithChapter:
    book = await create_test_book(
        db_session=db_session,
        user_id=DEFAULT_USER_ID,
        title="Test Book",
        author="Test Author",
    )
    chapter = models.Chapter(book_id=book.id, name="Chapter 1")
    db_session.add(chapter)
    await db_session.commit()
    await db_session.refresh(chapter)
    return BookWithChapter(book=book, chapter=chapter)


@pytest.fixture
async def book_with_highlights(db_session: AsyncSession) -> BookWithHighlights:
    book = await create_test_book(
        db_session=db_session,
        user_id=DEFAULT_USER_ID,
        title="Test Book",
        author="Test Author",
    )
    highlight1 = await create_test_highlight(
        db_session=db_session,
        book=book,
        user_id=DEFAULT_USER_ID,
        text="Highlight 1",
        page=10,
        datetime_str="2024-01-15 14:30:22",
    )
    highlight2 = await create_test_highlight(
        db_session=db_session,
        book=book,
        user_id=DEFAULT_USER_ID,
        text="Highlight 2",
        page=20,
        datetime_str="2024-01-15 15:00:00",
    )
    return BookWithHighlights(book=book, highlights=[highlight1, highlight2])


@pytest.fixture
async def book_with_chapter_and_highlight(db_session: AsyncSession) -> BookWithChapterAndHighlights:
    book = await create_test_book(
        db_session=db_session,
        user_id=DEFAULT_USER_ID,
        title="Test Book",
        author="Test Author",
        isbn="1234567890",
    )
    chapter = models.Chapter(book_id=book.id, name="Chapter 1")
    db_session.add(chapter)
    await db_session.commit()
    await db_session.refresh(chapter)

    highlight = await create_test_highlight(
        db_session=db_session,
        book=book,
        user_id=DEFAULT_USER_ID,
        chapter_id=chapter.id,
        text="Test highlight",
        page=10,
        datetime_str="2024-01-15 14:30:22",
    )
    return BookWithChapterAndHighlights(book=book, chapter=chapter, highlights=[highlight])


@pytest.fixture
async def book_with_soft_deleted_highlight(db_session: AsyncSession) -> BookWithHighlights:
    book = await create_test_book(
        db_session=db_session,
        user_id=DEFAULT_USER_ID,
        title="Test Book",
        author="Test Author",
        isbn="1234567890",
    )
    highlight = await create_test_highlight(
        db_session=db_session,
        book=book,
        user_id=DEFAULT_USER_ID,
        text="Deleted Highlight",
        page=10,
        datetime_str="2024-01-15 14:30:22",
        deleted_at=datetime.now(UTC),
    )
    return BookWithHighlights(book=book, highlights=[highlight])


class TestDeleteBook:
    """Test suite for DELETE /books/:id endpoint."""

    async def test_delete_book_success(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        book_with_chapter_and_highlight: BookWithChapterAndHighlights,
    ) -> None:
        """Test successful deletion of a book."""
        book = book_with_chapter_and_highlight.book

        response = await client.delete(f"/api/v1/books/{book.id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify book was deleted (cascade delete should handle chapters and highlights)
        result = await db_session.execute(select(models.Book).filter_by(id=book.id))
        deleted_book = result.scalar_one_or_none()
        assert deleted_book is None

        # Verify chapters were deleted
        result = await db_session.execute(select(models.Chapter).filter_by(book_id=book.id))
        chapters = result.scalars().all()
        assert len(chapters) == 0

        # Verify highlights were deleted
        result = await db_session.execute(select(models.Highlight).filter_by(book_id=book.id))
        highlights = result.scalars().all()
        assert len(highlights) == 0

    async def test_delete_book_cascades_to_its_embeddings_only(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        book_with_chapter_and_highlight: BookWithChapterAndHighlights,
    ) -> None:
        """Deleting a book must not leave its embeddings orphaned.

        Book deletion is a database-level cascade with no per-row application
        hook, so the foreign keys are the only thing that prunes them. Without
        them they would survive until the next backfill.
        """
        book = book_with_chapter_and_highlight.book
        doomed = book_with_chapter_and_highlight.highlights[0]
        survivor = await create_test_book(db_session, user_id=DEFAULT_USER_ID, title="Keep me")
        kept = await create_test_highlight(
            db_session,
            survivor,
            DEFAULT_USER_ID,
            text="keep",
            datetime_str="2024-01-15 14:30:22",
        )
        for target, highlight in ((book, doomed), (survivor, kept)):
            db_session.add(
                models.Embedding(
                    user_id=DEFAULT_USER_ID,
                    content_type="highlight",
                    content_id=highlight.id,
                    highlight_id=highlight.id,
                    book_id=target.id,
                    embedding=[0.1, 0.2],
                    model_name="bge-m3",
                    model_version="1",
                    content_hash="h" * 64,
                )
            )
        await db_session.commit()

        response = await client.delete(f"/api/v1/books/{book.id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        remaining = (await db_session.execute(select(models.Embedding))).scalars().all()
        assert [row.book_id for row in remaining] == [survivor.id]

    async def test_delete_book_not_found(self, client: AsyncClient) -> None:
        """Test deletion of non-existent book."""
        response = await client.delete("/api/v1/books/99999")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "not found" in data["message"].lower()


class TestDeleteHighlights:
    """Test suite for DELETE /books/:id/highlight endpoint."""

    async def test_soft_deleting_highlights_removes_their_embeddings(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        book_with_highlights: BookWithHighlights,
    ) -> None:
        """No FK can reach this: a soft delete is an UPDATE, so nothing cascades.

        The use case has to remove them explicitly, or they linger in the index
        until the next backfill.
        """
        book = book_with_highlights.book
        deleted, kept = book_with_highlights.highlights
        for highlight in (deleted, kept):
            await index_highlight(db_session, book, highlight)

        response = await client.request(
            "DELETE",
            f"/api/v1/books/{book.id}/highlight",
            json={"highlight_ids": [deleted.id]},
        )

        assert response.status_code == status.HTTP_200_OK
        remaining = (await db_session.execute(select(models.Embedding.content_id))).scalars().all()
        assert list(remaining) == [kept.id]

    async def test_leaves_embeddings_of_highlights_it_did_not_delete(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        book_with_highlights: BookWithHighlights,
    ) -> None:
        """The requested ids are unverified input, so only what was deleted may be pruned.

        A stranger's id used to erase their embedding while their highlight
        stayed live — their content silently vanished from semantic search until
        a full backfill. An id of one's own from another book did the same.
        """
        book = book_with_highlights.book
        mine, _ = book_with_highlights.highlights
        await index_highlight(db_session, book, mine)

        victim = models.User(email="victim@test.com")
        db_session.add(victim)
        await db_session.commit()
        await db_session.refresh(victim)
        their_book = await create_test_book(
            db_session=db_session, user_id=victim.id, title="Someone else's"
        )
        theirs = await plant_indexed_highlight(db_session, their_book, "theirs")

        my_other_book = await create_test_book(
            db_session=db_session, user_id=DEFAULT_USER_ID, title="My other book"
        )
        elsewhere = await plant_indexed_highlight(db_session, my_other_book, "elsewhere")

        response = await client.request(
            "DELETE",
            f"/api/v1/books/{book.id}/highlight",
            json={"highlight_ids": [mine.id, theirs.id, elsewhere.id]},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["deleted_count"] == 1
        surviving = (await db_session.execute(select(models.Embedding.content_id))).scalars().all()
        assert set(surviving) == {theirs.id, elsewhere.id}
        for untouched in (theirs, elsewhere):
            await db_session.refresh(untouched)
            assert untouched.deleted_at is None

    async def test_embedding_cleanup_failure_does_not_fail_the_delete(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        book_with_highlights: BookWithHighlights,
    ) -> None:
        """The soft delete commits first, and the two are not one transaction.

        Embedding bookkeeping must never fail a user write; the backfill sweep
        reconciles what this leaves behind.
        """
        book = book_with_highlights.book
        target, _ = book_with_highlights.highlights
        await index_highlight(db_session, book, target)

        with patch.object(
            EmbeddingRepository, "delete_for", AsyncMock(side_effect=RuntimeError("boom"))
        ):
            response = await client.request(
                "DELETE",
                f"/api/v1/books/{book.id}/highlight",
                json={"highlight_ids": [target.id]},
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["deleted_count"] == 1
        await db_session.refresh(target)
        assert target.deleted_at is not None

    async def test_delete_highlights_success(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        book_with_highlights: BookWithHighlights,
    ) -> None:
        """Test successful soft deletion of highlights."""
        book = book_with_highlights.book
        highlight1, highlight2 = book_with_highlights.highlights

        payload = {"highlight_ids": [highlight1.id, highlight2.id]}
        response = await client.request(
            "DELETE", f"/api/v1/books/{book.id}/highlight", json=payload
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["deleted_count"] == 2
        assert "Successfully deleted 2 highlight(s)" in data["message"]

        # Verify highlights were soft-deleted
        await db_session.refresh(highlight1)
        await db_session.refresh(highlight2)
        assert highlight1.deleted_at is not None
        assert highlight2.deleted_at is not None

    async def test_delete_highlights_partial(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        book_with_highlights: BookWithHighlights,
    ) -> None:
        """Test deletion of subset of highlights."""
        book = book_with_highlights.book
        highlight1, highlight2 = book_with_highlights.highlights

        payload = {"highlight_ids": [highlight1.id]}
        response = await client.request(
            "DELETE", f"/api/v1/books/{book.id}/highlight", json=payload
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["deleted_count"] == 1

        # Verify only first highlight was soft-deleted
        await db_session.refresh(highlight1)
        await db_session.refresh(highlight2)
        assert highlight1.deleted_at is not None
        assert highlight2.deleted_at is None

    async def test_delete_highlights_already_deleted(
        self,
        client: AsyncClient,
        book_with_soft_deleted_highlight: BookWithHighlights,
    ) -> None:
        """Test deletion of already soft-deleted highlights."""
        book = book_with_soft_deleted_highlight.book
        highlight = book_with_soft_deleted_highlight.highlights[0]

        payload = {"highlight_ids": [highlight.id]}
        response = await client.request(
            "DELETE", f"/api/v1/books/{book.id}/highlight", json=payload
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["deleted_count"] == 0  # Should not count already deleted highlights

    async def test_delete_highlights_wrong_book(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test deletion of highlights with wrong book ID."""
        # Create two books - this test needs specific setup for cross-book verification
        book1 = await create_test_book(
            db_session=db_session,
            user_id=DEFAULT_USER_ID,
            title="Book 1",
            author="Author 1",
        )
        book2 = await create_test_book(
            db_session=db_session,
            user_id=DEFAULT_USER_ID,
            title="Book 2",
            author="Author 2",
        )

        highlight1 = await create_test_highlight(
            db_session=db_session,
            book=book1,
            user_id=DEFAULT_USER_ID,
            text="Highlight from Book 1",
            page=10,
            datetime_str="2024-01-15 14:30:22",
        )

        # Try to delete book1's highlight using book2's ID
        payload = {"highlight_ids": [highlight1.id]}
        response = await client.request(
            "DELETE", f"/api/v1/books/{book2.id}/highlight", json=payload
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["deleted_count"] == 0  # Should not delete highlights from different book

        # Verify highlight was not deleted
        await db_session.refresh(highlight1)
        assert highlight1.deleted_at is None

    async def test_delete_highlights_book_not_found(self, client: AsyncClient) -> None:
        """Test deletion of highlights for non-existent book."""
        payload = {"highlight_ids": [1, 2, 3]}
        response = await client.request("DELETE", "/api/v1/books/99999/highlight", json=payload)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "not found" in data["message"].lower()

    async def test_delete_highlights_empty_list(
        self, client: AsyncClient, test_book: models.Book
    ) -> None:
        """Test deletion with empty highlight list."""
        payload = {"highlight_ids": []}
        response = await client.request(
            "DELETE", f"/api/v1/books/{test_book.id}/highlight", json=payload
        )

        # Should fail validation because of min_length=1
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestHighlightSyncWithSoftDelete:
    """Test suite for highlight sync with soft-deleted highlights."""

    async def test_sync_skips_soft_deleted_highlights(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Test that sync does not recreate soft-deleted highlights."""
        # Create book with soft-deleted highlight and matching client_book_id
        book = await create_test_book(
            db_session=db_session,
            user_id=DEFAULT_USER_ID,
            title="Test Book",
            author="Test Author",
            isbn="1234567890",
            client_book_id="test-client-book-id",
        )
        await create_test_highlight(
            db_session=db_session,
            book=book,
            user_id=DEFAULT_USER_ID,
            text="Deleted Highlight",
            page=10,
            datetime_str="2024-01-15 14:30:22",
            deleted_at=datetime.now(UTC),
        )

        # Try to sync the same highlight again
        payload = {
            "client_book_id": "test-client-book-id",
            "highlights": [
                {
                    "text": "Deleted Highlight",
                    "page": 10,
                    "datetime": "2024-01-15 14:30:22",
                },
            ],
        }

        response = await plugin_client.post("/api/v1/highlights/sync", json=payload)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["highlights_created"] == 0
        assert data["highlights_skipped"] == 1  # Should skip the soft-deleted highlight

        # Verify no new highlight was created (still only one, the soft-deleted one)
        result = await db_session.execute(select(models.Highlight).filter_by(book_id=book.id))
        highlights = result.scalars().all()
        assert len(highlights) == 1
        assert highlights[0].deleted_at is not None

    async def test_sync_creates_new_highlights_skips_deleted(
        self, plugin_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Test that sync creates new highlights but skips deleted ones."""
        # This test needs specific book without ISBN to test author-based matching
        book = await create_test_book(
            db_session=db_session,
            user_id=DEFAULT_USER_ID,
            title="Test Book",
            author="Test Author",
            client_book_id="test-client-book-id-2",
        )

        await create_test_highlight(
            db_session=db_session,
            book=book,
            user_id=DEFAULT_USER_ID,
            text="Deleted Highlight",
            page=10,
            datetime_str="2024-01-15 14:30:22",
            deleted_at=datetime.now(UTC),
        )

        # Sync with the deleted highlight and a new one
        payload = {
            "client_book_id": "test-client-book-id-2",
            "highlights": [
                {
                    "text": "Deleted Highlight",  # Should be skipped
                    "page": 10,
                    "datetime": "2024-01-15 14:30:22",
                },
                {
                    "text": "New Highlight",  # Should be created
                    "page": 20,
                    "datetime": "2024-01-15 15:00:00",
                },
            ],
        }

        response = await plugin_client.post("/api/v1/highlights/sync", json=payload)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["highlights_created"] == 1
        assert data["highlights_skipped"] == 1

        # Verify we have 2 highlights: 1 deleted, 1 active
        result = await db_session.execute(select(models.Highlight).filter_by(book_id=book.id))
        all_highlights = result.scalars().all()
        assert len(all_highlights) == 2

        active_highlights = [h for h in all_highlights if h.deleted_at is None]
        deleted_highlights = [h for h in all_highlights if h.deleted_at is not None]

        assert len(active_highlights) == 1
        assert active_highlights[0].text == "New Highlight"
        assert len(deleted_highlights) == 1
        assert deleted_highlights[0].text == "Deleted Highlight"


class TestGetBookDetails:
    """Test suite for GET /books/:id endpoint to verify soft-delete filtering."""

    async def test_get_book_details_excludes_deleted_highlights(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        book_with_chapter: BookWithChapter,
    ) -> None:
        """Test that book details endpoint excludes soft-deleted highlights."""
        book, chapter = book_with_chapter

        # Add active and deleted highlights to the chapter
        await create_test_highlight(
            db_session=db_session,
            book=book,
            user_id=DEFAULT_USER_ID,
            chapter_id=chapter.id,
            text="Active Highlight",
            page=10,
            datetime_str="2024-01-15 14:30:22",
        )
        await create_test_highlight(
            db_session=db_session,
            book=book,
            user_id=DEFAULT_USER_ID,
            chapter_id=chapter.id,
            text="Deleted Highlight",
            page=20,
            datetime_str="2024-01-15 15:00:00",
            deleted_at=datetime.now(UTC),
        )

        response = await client.get(f"/api/v1/books/{book.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify only active highlight is returned
        assert len(data["chapters"]) == 1
        assert len(data["chapters"][0]["highlights"]) == 1
        assert data["chapters"][0]["highlights"][0]["text"] == "Active Highlight"

    async def test_get_book_details_includes_tags(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        book_with_chapter: BookWithChapter,
    ) -> None:
        """Test that book details endpoint includes highlight tags for each highlight."""
        book, chapter = book_with_chapter

        highlight = await create_test_highlight(
            db_session=db_session,
            book=book,
            user_id=DEFAULT_USER_ID,
            chapter_id=chapter.id,
            text="Test Highlight",
            page=10,
            datetime_str="2024-01-15 14:30:22",
        )

        # Create highlight tags for the book
        tag1 = models.Tag(book_id=book.id, user_id=DEFAULT_USER_ID, name="Important")
        tag2 = models.Tag(book_id=book.id, user_id=DEFAULT_USER_ID, name="Review")
        db_session.add_all([tag1, tag2])
        await db_session.commit()
        await db_session.refresh(tag1)
        await db_session.refresh(tag2)

        # Associate tags with the highlight
        highlight.tags.append(tag1)
        highlight.tags.append(tag2)
        await db_session.commit()

        response = await client.get(f"/api/v1/books/{book.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify highlight tags are returned
        assert len(data["chapters"]) == 1
        assert len(data["chapters"][0]["highlights"]) == 1

        highlight_data = data["chapters"][0]["highlights"][0]
        assert "tags" in highlight_data
        assert len(highlight_data["tags"]) == 2

        tag_names = [tag["name"] for tag in highlight_data["tags"]]
        assert "Important" in tag_names
        assert "Review" in tag_names

    async def test_get_book_details_includes_note_only_tag(
        self,
        client: AsyncClient,
        test_book: models.Book,
    ) -> None:
        """A tag linked only to a note (never to a highlight) must still appear
        in the book-level tag list that feeds the tag-input dropdown."""
        tag_resp = await client.post(
            f"/api/v1/books/{test_book.id}/tag",
            json={"name": "note-only"},
        )
        assert tag_resp.status_code in (200, 201), tag_resp.text
        tag_id = tag_resp.json()["id"]

        await client.post(
            "/api/v1/notes",
            json={"title": "Concept", "book_id": test_book.id, "tag_ids": [tag_id]},
        )

        response = await client.get(f"/api/v1/books/{test_book.id}")
        assert response.status_code == status.HTTP_200_OK
        assert tag_id in [tag["id"] for tag in response.json()["tags"]]

    async def test_get_book_details_includes_reading_position(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        book_with_chapter: BookWithChapter,
    ) -> None:
        """Test that book details includes reading position from latest session."""
        book, _chapter = book_with_chapter

        session = models.ReadingSession(
            user_id=DEFAULT_USER_ID,
            book_id=book.id,
            start_time=datetime(2024, 1, 15, 14, 0, 0, tzinfo=UTC),
            end_time=datetime(2024, 1, 15, 15, 0, 0, tzinfo=UTC),
            start_position=[10, 0],
            end_position=[50, 100],
            content_hash="test-hash-reading-position",
        )
        db_session.add(session)
        await db_session.commit()

        response = await client.get(f"/api/v1/books/{book.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["reading_position"] == {"index": 50, "char_index": 100}

    async def test_get_book_details_reading_position_null_when_no_sessions(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        book_with_chapter: BookWithChapter,
    ) -> None:
        """Test that reading_position is null when no reading sessions exist."""
        book, _ = book_with_chapter

        response = await client.get(f"/api/v1/books/{book.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["reading_position"] is None

    async def test_get_book_details_includes_chapter_start_position(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        book_with_chapter: BookWithChapter,
    ) -> None:
        """Test that chapters include start_position."""
        book, chapter = book_with_chapter

        chapter.start_position = [25, 0]
        await db_session.commit()

        response = await client.get(f"/api/v1/books/{book.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["chapters"]) == 1
        assert data["chapters"][0]["start_position"] == {"index": 25, "char_index": 0}


class TestGetBooksWithFlashcardFilter:
    @pytest.fixture
    async def books_with_flashcards(self, db_session: AsyncSession) -> None:
        """Create test books: one with flashcards, one without."""
        book_with = await create_test_book(
            db_session=db_session,
            user_id=DEFAULT_USER_ID,
            title="Book with Flashcards",
            author="Author 1",
        )
        await create_test_book(
            db_session=db_session,
            user_id=DEFAULT_USER_ID,
            title="Book without Flashcards",
            author="Author 2",
        )

        # Add flashcard to first book
        flashcard = models.Flashcard(
            user_id=DEFAULT_USER_ID,
            book_id=book_with.id,
            question="Test question?",
            answer="Test answer",
        )
        db_session.add(flashcard)
        await db_session.commit()

    async def test_get_books_without_filter_returns_all(
        self, client: AsyncClient, books_with_flashcards: None
    ) -> None:
        """Test that without filter, all books are returned."""
        response = await client.get("/api/v1/books/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    async def test_get_books_with_flashcard_filter_returns_only_books_with_flashcards(
        self, client: AsyncClient, books_with_flashcards: None
    ) -> None:
        """Test that only_with_flashcards=true returns only books with flashcards."""
        response = await client.get("/api/v1/books/?only_with_flashcards=true")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "Book with Flashcards"
        assert data["items"][0]["flashcard_count"] == 1

    async def test_get_book_details_includes_book_flashcards(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        book_with_chapter: BookWithChapter,
    ) -> None:
        """Test that book details endpoint includes book-level flashcards."""
        book, chapter = book_with_chapter

        # Create a book-level flashcard (not associated with any highlight)
        flashcard = models.Flashcard(
            user_id=DEFAULT_USER_ID,
            book_id=book.id,
            question="What is the main theme?",
            answer="The main theme is resilience.",
        )
        db_session.add(flashcard)

        # Also create a highlight-based flashcard to ensure it's NOT included in book_flashcards
        highlight = await create_test_highlight(
            db_session=db_session,
            book=book,
            user_id=DEFAULT_USER_ID,
            chapter_id=chapter.id,
            text="Important passage",
            page=5,
            datetime_str="2024-01-01 12:00:00",
        )
        highlight_flashcard = models.Flashcard(
            user_id=DEFAULT_USER_ID,
            book_id=book.id,
            highlight_id=highlight.id,
            question="What does this highlight mean?",
            answer="It means something important.",
        )
        db_session.add(highlight_flashcard)
        await db_session.commit()

        response = await client.get(f"/api/v1/books/{book.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify book_flashcards field exists and contains only book-level flashcards
        assert "book_flashcards" in data, "book_flashcards field is missing from response"
        assert len(data["book_flashcards"]) == 1
        book_fc = data["book_flashcards"][0]
        assert book_fc["question"] == "What is the main theme?"
        assert book_fc["answer"] == "The main theme is resilience."
        assert book_fc["book_id"] == book.id
        assert book_fc["highlight_id"] is None

        # Verify the highlight flashcard is in the chapter's highlights, not in book_flashcards
        assert len(data["chapters"]) == 1
        assert len(data["chapters"][0]["highlights"]) == 1
        assert len(data["chapters"][0]["highlights"][0]["flashcards"]) == 1
        highlight_fc = data["chapters"][0]["highlights"][0]["flashcards"][0]
        assert highlight_fc["question"] == "What does this highlight mean?"


class TestReadingStage:
    """Test suite for PUT /books/{book_id}/reading-stage endpoint."""

    async def test_reading_stage_defaults_to_null(
        self, client: AsyncClient, test_book: models.Book
    ) -> None:
        response = await client.get(f"/api/v1/books/{test_book.id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["reading_stage"] is None

    @pytest.mark.parametrize(
        "stage",
        ["to_read", "skimming", "reading", "finished", "reflected", "did_not_finish"],
    )
    async def test_set_reading_stage(
        self, client: AsyncClient, test_book: models.Book, stage: str
    ) -> None:
        response = await client.put(
            f"/api/v1/books/{test_book.id}/reading-stage",
            json={"reading_stage": stage},
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        details = await client.get(f"/api/v1/books/{test_book.id}")
        assert details.json()["reading_stage"] == stage

    async def test_clear_reading_stage(self, client: AsyncClient, test_book: models.Book) -> None:
        await client.put(
            f"/api/v1/books/{test_book.id}/reading-stage",
            json={"reading_stage": "finished"},
        )
        response = await client.put(
            f"/api/v1/books/{test_book.id}/reading-stage",
            json={"reading_stage": None},
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        details = await client.get(f"/api/v1/books/{test_book.id}")
        assert details.json()["reading_stage"] is None

    async def test_invalid_reading_stage_rejected(
        self, client: AsyncClient, test_book: models.Book
    ) -> None:
        response = await client.put(
            f"/api/v1/books/{test_book.id}/reading-stage",
            json={"reading_stage": "not-a-stage"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_reading_stage_book_not_found(self, client: AsyncClient) -> None:
        response = await client.put(
            "/api/v1/books/99999/reading-stage",
            json={"reading_stage": "reading"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
