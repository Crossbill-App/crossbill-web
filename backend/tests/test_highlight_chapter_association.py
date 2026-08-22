"""Tests for highlight-chapter association with duplicate chapter names."""

from _pytest.logging import LogCaptureFixture
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src import models
from tests.conftest import create_test_book


class TestHighlightChapterAssociation:
    """Test suite for highlight-chapter association using chapter_number."""

    async def test_highlight_association_with_duplicate_names_using_chapter_number(
        self, plugin_client: AsyncClient, db_session: AsyncSession, test_user: models.User
    ) -> None:
        """Test that highlights are correctly associated when duplicate chapter names exist.

        This is the core test for the fix. When a book has multiple chapters with
        the same name (e.g., "Harjoitukset" under Part I and Part II), highlights
        should be associated with the correct chapter based on chapter_number.
        """
        # Create a test book with matching client_book_id
        book = await create_test_book(
            db_session=db_session,
            user_id=test_user.id,
            title="Test Book with Duplicate Chapters",
            author="Test Author",
            client_book_id="test-client-duplicate-chapters",
        )

        # Create two chapters with the same name but different chapter_numbers
        # (simulating hierarchical ToC from EPUB)
        chapter_part1 = models.Chapter(
            book_id=book.id,
            name="Harjoitukset",
            chapter_number=2,
            parent_id=None,  # Under Part I
        )
        chapter_part2 = models.Chapter(
            book_id=book.id,
            name="Harjoitukset",
            chapter_number=4,
            parent_id=None,  # Under Part II
        )
        db_session.add(chapter_part1)
        db_session.add(chapter_part2)
        await db_session.commit()
        await db_session.refresh(chapter_part1)
        await db_session.refresh(chapter_part2)

        # Upload highlights with chapter_number specified
        payload = {
            "client_book_id": "test-client-duplicate-chapters",
            "highlights": [
                {
                    "text": "Highlight in Part I exercises",
                    "chapter": "Harjoitukset",
                    "chapter_number": 2,  # References Part I
                    "page": 10,
                    "datetime": "2024-01-15 14:00:00",
                },
                {
                    "text": "Highlight in Part II exercises",
                    "chapter": "Harjoitukset",
                    "chapter_number": 4,  # References Part II
                    "page": 50,
                    "datetime": "2024-01-15 15:00:00",
                },
                {
                    "text": "Another highlight in Part I exercises",
                    "chapter": "Harjoitukset",
                    "chapter_number": 2,  # References Part I again
                    "page": 15,
                    "datetime": "2024-01-15 16:00:00",
                },
            ],
        }

        response = await plugin_client.post("/api/v1/highlights/upload", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["highlights_created"] == 3
        assert data["highlights_skipped"] == 0

        # Verify highlights are associated with the correct chapters
        result = await db_session.execute(
            select(models.Highlight).filter_by(book_id=book.id).order_by(models.Highlight.page)
        )
        highlights = result.scalars().all()
        assert len(highlights) == 3

        # First highlight should be associated with Part I (chapter_number=2)
        assert highlights[0].text == "Highlight in Part I exercises"
        assert highlights[0].chapter_id == chapter_part1.id
        assert highlights[0].chapter is not None
        assert highlights[0].chapter.chapter_number == 2

        # Second highlight should be associated with Part I again (chapter_number=2)
        assert highlights[1].text == "Another highlight in Part I exercises"
        assert highlights[1].chapter_id == chapter_part1.id
        assert highlights[1].chapter is not None
        assert highlights[1].chapter.chapter_number == 2

        # Third highlight should be associated with Part II (chapter_number=4)
        assert highlights[2].text == "Highlight in Part II exercises"
        assert highlights[2].chapter_id == chapter_part2.id
        assert highlights[2].chapter is not None
        assert highlights[2].chapter.chapter_number == 4

    async def test_highlight_without_chapter_number_logs_warning(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        test_user: models.User,
        caplog: LogCaptureFixture,
    ) -> None:
        """Test that highlights without chapter_number log a warning.

        When a highlight has a chapter name but no chapter_number, it should
        log a warning and create the highlight without chapter association.
        """
        # Create a test book with matching client_book_id
        book = await create_test_book(
            db_session=db_session,
            user_id=test_user.id,
            title="Test Book for Missing Chapter Number",
            author="Test Author",
            client_book_id="test-client-missing-number",
        )

        # Create a chapter
        chapter = models.Chapter(
            book_id=book.id,
            name="Chapter 1",
            chapter_number=1,
        )
        db_session.add(chapter)
        await db_session.commit()

        # Upload highlight without chapter_number
        payload = {
            "client_book_id": "test-client-missing-number",
            "highlights": [
                {
                    "text": "Highlight without chapter_number",
                    "chapter": "Chapter 1",
                    # No chapter_number provided
                    "page": 10,
                    "datetime": "2024-01-15 14:00:00",
                },
            ],
        }

        response = await plugin_client.post("/api/v1/highlights/upload", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["highlights_created"] == 1

        # Verify highlight was created without chapter association
        result = await db_session.execute(select(models.Highlight).filter_by(book_id=book.id))
        highlight = result.scalar_one_or_none()
        assert highlight is not None
        assert highlight.text == "Highlight without chapter_number"
        assert highlight.chapter_id is None  # No chapter association

        # Check that warning was logged
        assert any(
            "highlight_missing_chapter_number" in record.message for record in caplog.records
        )

    async def test_mixed_highlights_with_and_without_chapter_numbers(
        self, plugin_client: AsyncClient, db_session: AsyncSession, test_user: models.User
    ) -> None:
        """Test uploading a mix of highlights with and without chapter_numbers.

        This tests the real-world scenario where some highlights might have
        chapter_numbers and others might not.
        """
        # Create a test book with matching client_book_id
        book = await create_test_book(
            db_session=db_session,
            user_id=test_user.id,
            title="Test Book Mixed Chapter Numbers",
            author="Test Author",
            client_book_id="test-client-mixed",
        )

        # Create a chapter
        chapter1 = models.Chapter(book_id=book.id, name="Chapter 1", chapter_number=1)
        db_session.add(chapter1)
        await db_session.commit()
        await db_session.refresh(chapter1)

        # Upload highlights - some with chapter_number, some without
        payload = {
            "client_book_id": "test-client-mixed",
            "highlights": [
                {
                    "text": "Highlight with chapter_number",
                    "chapter": "Chapter 1",
                    "chapter_number": 1,
                    "page": 10,
                    "datetime": "2024-01-15 14:00:00",
                },
                {
                    "text": "Highlight without chapter_number",
                    "chapter": "Chapter 1",
                    # No chapter_number
                    "page": 15,
                    "datetime": "2024-01-15 15:00:00",
                },
                {
                    "text": "Highlight with no chapter at all",
                    # No chapter or chapter_number
                    "page": 20,
                    "datetime": "2024-01-15 16:00:00",
                },
            ],
        }

        response = await plugin_client.post("/api/v1/highlights/upload", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["highlights_created"] == 3

        # Verify associations
        result = await db_session.execute(
            select(models.Highlight).filter_by(book_id=book.id).order_by(models.Highlight.page)
        )
        highlights = result.scalars().all()
        assert len(highlights) == 3

        # First highlight should be associated (has chapter_number)
        assert highlights[0].text == "Highlight with chapter_number"
        assert highlights[0].chapter_id == chapter1.id

        # Second highlight should NOT be associated (no chapter_number)
        assert highlights[1].text == "Highlight without chapter_number"
        assert highlights[1].chapter_id is None

        # Third highlight should NOT be associated (no chapter at all)
        assert highlights[2].text == "Highlight with no chapter at all"
        assert highlights[2].chapter_id is None
