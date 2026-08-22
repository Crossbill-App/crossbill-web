"""Tests for highlights API endpoints."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src import models
from tests.conftest import (
    CreateBookFunc,
    create_test_book,
    create_test_chapter,
    create_test_highlight,
)


async def resync_edited_highlight(
    plugin_client: AsyncClient,
    db_session: AsyncSession,
    create_book_via_api: CreateBookFunc,
    client_book_id: str,
    first: dict[str, Any],
    edited: dict[str, Any],
) -> models.Highlight:
    """Upload a highlight, then re-upload the copy a device has since edited.

    Returns the stored row, which the second upload skipped as a duplicate.
    """
    await create_book_via_api({"client_book_id": client_book_id, "title": client_book_id})

    created = await plugin_client.post(
        "/api/v1/highlights/upload",
        json={"client_book_id": client_book_id, "highlights": [first]},
    )
    assert created.json()["highlights_created"] == 1

    resynced = await plugin_client.post(
        "/api/v1/highlights/upload",
        json={"client_book_id": client_book_id, "highlights": [edited]},
    )
    assert resynced.json()["highlights_created"] == 0
    assert resynced.json()["highlights_skipped"] == 1

    result = await db_session.execute(select(models.Highlight).filter_by(text=first["text"]))
    return result.scalar_one()


async def upload_then_delete_highlight(
    plugin_client: AsyncClient,
    db_session: AsyncSession,
    client_book_id: str,
    book_id: int,
    highlight: dict[str, Any],
) -> None:
    """Upload one highlight and soft-delete it again, as a reader would."""
    upload = await plugin_client.post(
        "/api/v1/highlights/upload",
        json={"client_book_id": client_book_id, "highlights": [highlight]},
    )
    assert upload.json()["highlights_created"] == 1

    result = await db_session.execute(select(models.Highlight).filter_by(text=highlight["text"]))
    deletion = await plugin_client.request(
        "DELETE",
        f"/api/v1/books/{book_id}/highlight",
        json={"highlight_ids": [result.scalar_one().id]},
    )
    assert deletion.json()["deleted_count"] == 1


class TestHighlightsUpload:
    """Test suite for highlights upload endpoint."""

    async def test_upload_highlights_success(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        create_book_via_api: CreateBookFunc,
    ) -> None:
        """Test successful upload of highlights."""
        # Create the book via the fixture
        await create_book_via_api(
            {
                "client_book_id": "test-client-book-id",
                "title": "Test Book",
                "author": "Test Author",
                "isbn": "1234567890",
            }
        )

        # Upload highlights
        payload = {
            "client_book_id": "test-client-book-id",
            "highlights": [
                {
                    "text": "Test highlight 1",
                    "chapter": "Chapter 1",
                    "page": 10,
                    "datetime": "2024-01-15 14:30:22",
                },
                {
                    "text": "Test highlight 2",
                    "chapter": "Chapter 2",
                    "page": 25,
                    "datetime": "2024-01-15 15:00:00",
                },
            ],
        }

        response = await plugin_client.post("/api/v1/highlights/upload", json=payload)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["highlights_created"] == 2
        assert data["highlights_skipped"] == 0
        assert "book_id" in data
        assert "Successfully synced highlights" in data["message"]

        # Verify book was created in database
        result = await db_session.execute(
            select(models.Book).filter_by(title="Test Book", author="Test Author")
        )
        book = result.scalar_one_or_none()
        assert book is not None
        assert book.title == "Test Book"
        assert book.author == "Test Author"
        assert book.isbn == "1234567890"

        # Verify highlights were created
        result = await db_session.execute(select(models.Highlight).filter_by(book_id=book.id))
        highlights = result.scalars().all()
        assert len(highlights) == 2

        # Verify NO chapters were created (highlights without chapter_number don't create chapters)
        result = await db_session.execute(select(models.Chapter).filter_by(book_id=book.id))
        chapters = result.scalars().all()
        assert len(chapters) == 0

        # Verify highlights have no chapter association (no chapter_number provided)
        for highlight in highlights:
            assert highlight.chapter_id is None

    async def test_upload_highlights_with_xpoints(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        create_book_via_api: CreateBookFunc,
    ) -> None:
        """Test uploading highlights with start_xpoint and end_xpoint fields."""
        # Create the book
        await create_book_via_api(
            {
                "client_book_id": "test-client-book-xpoints",
                "title": "Test Book With Xpoints",
                "author": "Test Author",
            }
        )

        # Upload highlights
        payload = {
            "client_book_id": "test-client-book-xpoints",
            "highlights": [
                {
                    "text": "Highlight with xpoints",
                    "chapter": "Chapter 1",
                    "page": 10,
                    "start_xpoint": "/body/div[1]/p[5]/text()[1].0",
                    "end_xpoint": "/body/div[1]/p[5]/text()[1].42",
                    "datetime": "2024-01-15 14:30:22",
                },
                {
                    "text": "Highlight without xpoints",
                    "chapter": "Chapter 2",
                    "page": 20,
                    "datetime": "2024-01-15 15:00:00",
                },
            ],
        }

        response = await plugin_client.post("/api/v1/highlights/upload", json=payload)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["highlights_created"] == 2

        # Verify xpoints were stored in database
        result = await db_session.execute(
            select(models.Book).filter_by(title="Test Book With Xpoints", author="Test Author")
        )
        book = result.scalar_one_or_none()
        assert book is not None

        result = await db_session.execute(
            select(models.Highlight).filter_by(book_id=book.id).order_by(models.Highlight.page)
        )
        highlights = result.scalars().all()
        assert len(highlights) == 2

        # First highlight should have xpoints
        # Note: XPoint value object normalizes text()[1].0 (defaults) to just xpath
        assert highlights[0].start_xpoint == "/body/DocFragment[1]/body/div[1]/p[5]"
        assert highlights[0].end_xpoint == "/body/DocFragment[1]/body/div[1]/p[5]/text().42"

        # Second highlight should have null xpoints
        assert highlights[1].start_xpoint is None
        assert highlights[1].end_xpoint is None

    async def test_upload_keeps_device_datetime_and_note(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        create_book_via_api: CreateBookFunc,
    ) -> None:
        """The e-reader's own datetime and note are stored, not replaced by server values."""
        await create_book_via_api(
            {
                "client_book_id": "test-client-book-device-fields",
                "title": "Device Fields Book",
                "author": "Test Author",
            }
        )

        payload = {
            "client_book_id": "test-client-book-device-fields",
            "device_id": "Kobo Clara",
            "highlights": [
                {
                    "text": "Annotated on the device",
                    "datetime": "2019-06-01 08:15:30",
                    "note": "Read this again before chapter 3",
                },
                {
                    "text": "No note here",
                    "datetime": "2019-06-01 08:16:00",
                },
            ],
        }

        response = await plugin_client.post("/api/v1/highlights/upload", json=payload)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["highlights_created"] == 2

        result = await db_session.execute(
            select(models.Highlight).order_by(models.Highlight.datetime)
        )
        highlights = result.scalars().all()
        assert [h.datetime for h in highlights] == ["2019-06-01 08:15:30", "2019-06-01 08:16:00"]
        assert highlights[0].koreader_note == "Read this again before chapter 3"
        assert highlights[1].koreader_note is None
        # The device id is per batch, so every highlight in it carries the same one.
        assert [h.origin_device_id for h in highlights] == ["Kobo Clara", "Kobo Clara"]

    async def test_upload_without_device_id_stores_none(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        create_book_via_api: CreateBookFunc,
    ) -> None:
        """Older plugins send no device_id; the highlight simply has no origin."""
        await create_book_via_api(
            {
                "client_book_id": "test-client-book-no-device",
                "title": "No Device Book",
                "author": "Test Author",
            }
        )

        response = await plugin_client.post(
            "/api/v1/highlights/upload",
            json={
                "client_book_id": "test-client-book-no-device",
                "highlights": [
                    {"text": "From an unnamed device", "datetime": "2019-06-01 08:15:30"}
                ],
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["highlights_created"] == 1

        result = await db_session.execute(
            select(models.Highlight).filter_by(text="From an unnamed device")
        )
        assert result.scalar_one().origin_device_id is None

    async def test_reupload_applies_a_newer_note_edit(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        create_book_via_api: CreateBookFunc,
    ) -> None:
        """The highlight itself is still skipped, but a later device edit lands."""
        highlight = {"text": "Same passage", "datetime": "2019-06-01 08:15:30"}

        stored = await resync_edited_highlight(
            plugin_client,
            db_session,
            create_book_via_api,
            "test-client-book-note-rewrite",
            {**highlight, "note": "first note"},
            {**highlight, "note": "edited note", "datetime_updated": "2019-06-02 09:00:00"},
        )

        assert stored.koreader_note == "edited note"
        assert stored.koreader_updated_at == "2019-06-02 09:00:00"

    async def test_reupload_ignores_an_older_note_edit(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        create_book_via_api: CreateBookFunc,
    ) -> None:
        """A device syncing its stale copy must not undo a newer edit from elsewhere."""
        highlight = {"text": "Passage edited elsewhere", "datetime": "2019-06-01 08:15:30"}

        stored = await resync_edited_highlight(
            plugin_client,
            db_session,
            create_book_via_api,
            "test-client-book-note-stale",
            {**highlight, "note": "newer note", "datetime_updated": "2019-06-05 10:00:00"},
            {**highlight, "note": "stale note", "datetime_updated": "2019-06-02 09:00:00"},
        )

        assert stored.koreader_note == "newer note"
        assert stored.koreader_updated_at == "2019-06-05 10:00:00"

    async def test_first_edit_is_accepted_even_when_older_than_the_stored_datetime(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        create_book_via_api: CreateBookFunc,
    ) -> None:
        """A row that never received a device edit has nothing to protect.

        Rows uploaded before notes were kept carry a server-side datetime that
        a note written on the device before that upload would never beat.
        """
        stored = await resync_edited_highlight(
            plugin_client,
            db_session,
            create_book_via_api,
            "test-client-book-first-edit",
            {"text": "Noted before first upload", "datetime": "2025-11-17 20:21:54"},
            {
                "text": "Noted before first upload",
                "datetime": "2025-11-17 20:21:54",
                "note": "written in June",
                "datetime_updated": "2025-06-01 09:00:00",
            },
        )

        assert stored.koreader_note == "written in June"
        assert stored.koreader_updated_at == "2025-06-01 09:00:00"

    async def test_reupload_with_the_same_edit_time_keeps_the_stored_note(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        create_book_via_api: CreateBookFunc,
    ) -> None:
        """Equal timestamps are not newer, so the server's copy stands."""
        highlight = {
            "text": "Passage edited at the same second",
            "datetime": "2019-06-01 08:15:30",
            "datetime_updated": "2019-06-05 10:00:00",
        }

        stored = await resync_edited_highlight(
            plugin_client,
            db_session,
            create_book_via_api,
            "test-client-book-note-tie",
            {**highlight, "note": "note on the server"},
            {**highlight, "note": "note from the device"},
        )

        assert stored.koreader_note == "note on the server"

    async def test_reupload_without_an_edit_time_compares_creation_datetimes(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        create_book_via_api: CreateBookFunc,
    ) -> None:
        """A highlight never edited on the device carries only its creation time."""
        stored = await resync_edited_highlight(
            plugin_client,
            db_session,
            create_book_via_api,
            "test-client-book-note-no-edit-time",
            {
                "text": "Passage from an older sidecar",
                "datetime": "2019-06-01 08:15:30",
                "note": "first note",
            },
            {
                "text": "Passage from an older sidecar",
                "datetime": "2019-06-02 08:15:30",
                "note": "note from the newer copy",
            },
        )

        assert stored.koreader_note == "note from the newer copy"
        assert stored.koreader_updated_at == "2019-06-02 08:15:30"

    async def test_reupload_applies_a_newer_style_change(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        create_book_via_api: CreateBookFunc,
    ) -> None:
        """Recolouring a highlight on the device moves it to the new style."""
        highlight = {"text": "Passage recoloured", "datetime": "2019-06-01 08:15:30"}

        stored = await resync_edited_highlight(
            plugin_client,
            db_session,
            create_book_via_api,
            "test-client-book-style-change",
            {**highlight, "color": "yellow", "drawer": "lighten"},
            {
                **highlight,
                "color": "red",
                "drawer": "underscore",
                "datetime_updated": "2019-06-02 09:00:00",
            },
        )

        result = await db_session.execute(
            select(models.HighlightStyle).filter_by(id=stored.highlight_style_id)
        )
        style = result.scalar_one()
        assert style.device_color == "red"
        assert style.device_style == "underscore"

    async def test_reupload_without_note_clears_stored_note(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        create_book_via_api: CreateBookFunc,
    ) -> None:
        """Deleting the note on the device clears it on the server too."""
        highlight = {"text": "Passage once annotated", "datetime": "2019-06-01 08:15:30"}

        stored = await resync_edited_highlight(
            plugin_client,
            db_session,
            create_book_via_api,
            "test-client-book-note-clearing",
            {**highlight, "note": "note to be removed"},
            {**highlight, "datetime_updated": "2019-06-02 09:00:00"},
        )

        assert stored.koreader_note is None

    async def test_reupload_leaves_soft_deleted_duplicate_alone(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        create_book_via_api: CreateBookFunc,
    ) -> None:
        """A deleted highlight stays deleted and keeps its note; it is not revived."""
        book = await create_book_via_api(
            {
                "client_book_id": "test-client-book-note-deleted",
                "title": "Deleted Note Book",
                "author": "Test Author",
            }
        )
        highlight = {"text": "Deleted passage", "datetime": "2019-06-01 08:15:30"}

        await upload_then_delete_highlight(
            plugin_client,
            db_session,
            "test-client-book-note-deleted",
            book.book_id,
            {**highlight, "note": "note on a deleted highlight"},
        )

        second = await plugin_client.post(
            "/api/v1/highlights/upload",
            json={
                "client_book_id": "test-client-book-note-deleted",
                "highlights": [
                    {
                        **highlight,
                        "note": "edited on the device",
                        "datetime_updated": "2019-06-02 09:00:00",
                    }
                ],
            },
        )
        assert second.json()["highlights_created"] == 0
        assert second.json()["highlights_skipped"] == 1

        result = await db_session.execute(
            select(models.Highlight).filter_by(text="Deleted passage")
        )
        stored = result.scalar_one()
        assert stored.deleted_at is not None
        assert stored.koreader_note == "note on a deleted highlight"

    async def test_reupload_fills_missing_xpoints(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        create_book_via_api: CreateBookFunc,
    ) -> None:
        """A highlight stored before the device sent xpoints gets them from a re-upload."""
        await create_book_via_api(
            {
                "client_book_id": "test-client-book-xpoint-backfill",
                "title": "Xpoint Backfill Book",
                "author": "Test Author",
            }
        )
        highlight = {"text": "Passage without xpoints", "datetime": "2019-06-01 08:15:30"}

        first = await plugin_client.post(
            "/api/v1/highlights/upload",
            json={
                "client_book_id": "test-client-book-xpoint-backfill",
                "highlights": [highlight],
            },
        )
        assert first.json()["highlights_created"] == 1

        second = await plugin_client.post(
            "/api/v1/highlights/upload",
            json={
                "client_book_id": "test-client-book-xpoint-backfill",
                "highlights": [
                    {
                        **highlight,
                        "start_xpoint": "/body/DocFragment[2]/body/p[1]/text().0",
                        "end_xpoint": "/body/DocFragment[2]/body/p[1]/text().13",
                    }
                ],
            },
        )
        assert second.json()["highlights_created"] == 0
        assert second.json()["highlights_skipped"] == 1

        result = await db_session.execute(
            select(models.Highlight).filter_by(text="Passage without xpoints")
        )
        stored = result.scalar_one()
        assert stored.start_xpoint == "/body/DocFragment[2]/body/p[1]"
        assert stored.end_xpoint == "/body/DocFragment[2]/body/p[1]/text().13"

    async def test_reupload_does_not_overwrite_existing_xpoints(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        create_book_via_api: CreateBookFunc,
    ) -> None:
        """Xpoints already stored stay put; only a missing pair is filled in."""
        await create_book_via_api(
            {
                "client_book_id": "test-client-book-xpoint-keeping",
                "title": "Xpoint Keeping Book",
                "author": "Test Author",
            }
        )
        highlight = {"text": "Passage anchored once", "datetime": "2019-06-01 08:15:30"}

        first = await plugin_client.post(
            "/api/v1/highlights/upload",
            json={
                "client_book_id": "test-client-book-xpoint-keeping",
                "highlights": [
                    {
                        **highlight,
                        "start_xpoint": "/body/DocFragment[2]/body/p[1]/text().0",
                        "end_xpoint": "/body/DocFragment[2]/body/p[1]/text().13",
                    }
                ],
            },
        )
        assert first.json()["highlights_created"] == 1

        second = await plugin_client.post(
            "/api/v1/highlights/upload",
            json={
                "client_book_id": "test-client-book-xpoint-keeping",
                "highlights": [
                    {
                        **highlight,
                        "start_xpoint": "/body/DocFragment[7]/body/p[9]/text().4",
                        "end_xpoint": "/body/DocFragment[7]/body/p[9]/text().20",
                    }
                ],
            },
        )
        assert second.json()["highlights_skipped"] == 1

        result = await db_session.execute(
            select(models.Highlight).filter_by(text="Passage anchored once")
        )
        stored = result.scalar_one()
        assert stored.start_xpoint == "/body/DocFragment[2]/body/p[1]"
        assert stored.end_xpoint == "/body/DocFragment[2]/body/p[1]/text().13"

    async def test_reupload_with_xpoints_resolves_position_when_epub_present(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        create_book_via_api: CreateBookFunc,
        epub_bytes: bytes,
        storage_dir: Path,
    ) -> None:
        """The backfilled xpoints are resolved against the book's EPUB into a position."""
        await create_book_via_api(
            {
                "client_book_id": "test-client-book-position-backfill",
                "title": "Position Backfill Book",
                "author": "Test Author",
            }
        )
        epub_upload = await plugin_client.post(
            "/api/v1/ereader/books/test-client-book-position-backfill/epub",
            files={"epub": ("book.epub", epub_bytes, "application/epub+zip")},
        )
        assert epub_upload.status_code == status.HTTP_200_OK

        highlight = {"text": "Some content.", "datetime": "2019-06-01 08:15:30"}
        first = await plugin_client.post(
            "/api/v1/highlights/upload",
            json={
                "client_book_id": "test-client-book-position-backfill",
                "highlights": [highlight],
            },
        )
        assert first.json()["highlights_created"] == 1

        result = await db_session.execute(select(models.Highlight).filter_by(text="Some content."))
        assert result.scalar_one().position is None

        second = await plugin_client.post(
            "/api/v1/highlights/upload",
            json={
                "client_book_id": "test-client-book-position-backfill",
                "highlights": [
                    {
                        **highlight,
                        "start_xpoint": "/body/DocFragment[2]/body/p[1]/text().0",
                        "end_xpoint": "/body/DocFragment[2]/body/p[1]/text().13",
                    }
                ],
            },
        )
        assert second.json()["highlights_skipped"] == 1

        db_session.expire_all()
        result = await db_session.execute(select(models.Highlight).filter_by(text="Some content."))
        assert result.scalar_one().position is not None

    async def test_reupload_leaves_soft_deleted_duplicate_unplaced(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        create_book_via_api: CreateBookFunc,
    ) -> None:
        """A deleted highlight is not given xpoints: it must stay out of the book."""
        book = await create_book_via_api(
            {
                "client_book_id": "test-client-book-xpoint-deleted",
                "title": "Deleted Xpoint Book",
                "author": "Test Author",
            }
        )
        highlight = {"text": "Deleted unplaced passage", "datetime": "2019-06-01 08:15:30"}

        await upload_then_delete_highlight(
            plugin_client, db_session, "test-client-book-xpoint-deleted", book.book_id, highlight
        )

        second = await plugin_client.post(
            "/api/v1/highlights/upload",
            json={
                "client_book_id": "test-client-book-xpoint-deleted",
                "highlights": [
                    {
                        **highlight,
                        "start_xpoint": "/body/DocFragment[2]/body/p[1]/text().0",
                        "end_xpoint": "/body/DocFragment[2]/body/p[1]/text().13",
                    }
                ],
            },
        )
        assert second.json()["highlights_skipped"] == 1

        result = await db_session.execute(
            select(models.Highlight).filter_by(text="Deleted unplaced passage")
        )
        stored = result.scalar_one()
        assert stored.deleted_at is not None
        assert stored.start_xpoint is None
        assert stored.end_xpoint is None

    async def test_upload_duplicate_highlights(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        create_book_via_api: CreateBookFunc,
    ) -> None:
        """Test that duplicate highlights are properly skipped."""
        # Create the book
        await create_book_via_api(
            {
                "client_book_id": "test-client-duplicate-book",
                "title": "Duplicate Test Book",
                "author": "Test Author",
            }
        )

        payload = {
            "client_book_id": "test-client-duplicate-book",
            "highlights": [
                {
                    "text": "Duplicate highlight",
                    "chapter": "Chapter 1",
                    "datetime": "2024-01-15 15:00:00",
                },
            ],
        }

        # First upload
        response1 = await plugin_client.post("/api/v1/highlights/upload", json=payload)
        assert response1.status_code == status.HTTP_200_OK
        data1 = response1.json()
        assert data1["highlights_created"] == 1
        assert data1["highlights_skipped"] == 0

        # Second upload (should skip duplicate)
        response2 = await plugin_client.post("/api/v1/highlights/upload", json=payload)
        assert response2.status_code == status.HTTP_200_OK
        data2 = response2.json()
        assert data2["highlights_created"] == 0
        assert data2["highlights_skipped"] == 1

        # Verify only one highlight exists in database
        result = await db_session.execute(
            select(models.Book).filter_by(title="Duplicate Test Book", author="Test Author")
        )
        book = result.scalar_one_or_none()
        assert book is not None
        result = await db_session.execute(select(models.Highlight).filter_by(book_id=book.id))
        highlights = result.scalars().all()
        assert len(highlights) == 1

    async def test_upload_partial_duplicates(
        self, plugin_client: AsyncClient, create_book_via_api: CreateBookFunc
    ) -> None:
        """Test uploading mix of new and duplicate highlights."""
        # Create the book
        await create_book_via_api(
            {
                "client_book_id": "test-client-partial-dup",
                "title": "Partial Duplicate Test Book",
                "author": "Test Author",
            }
        )

        # First upload
        payload1 = {
            "client_book_id": "test-client-partial-dup",
            "highlights": [
                {
                    "text": "Highlight 1",
                    "datetime": "2024-01-15 14:00:00",
                },
                {
                    "text": "Highlight 2",
                    "datetime": "2024-01-15 15:00:00",
                },
            ],
        }

        response1 = await plugin_client.post("/api/v1/highlights/upload", json=payload1)
        assert response1.status_code == status.HTTP_200_OK
        assert response1.json()["highlights_created"] == 2

        # Second upload with mix of new and duplicate
        payload2 = {
            "client_book_id": "test-client-partial-dup",
            "highlights": [
                {
                    "text": "Highlight 1",  # Duplicate
                    "datetime": "2024-01-15 14:00:00",
                },
                {
                    "text": "Highlight 3",  # New
                    "datetime": "2024-01-15 16:00:00",
                },
            ],
        }

        response2 = await plugin_client.post("/api/v1/highlights/upload", json=payload2)
        assert response2.status_code == status.HTTP_200_OK
        data2 = response2.json()
        assert data2["highlights_created"] == 1
        assert data2["highlights_skipped"] == 1

    async def test_upload_empty_highlights_list(
        self, plugin_client: AsyncClient, create_book_via_api: CreateBookFunc
    ) -> None:
        """Test uploading with empty highlights list."""
        # Create the book
        await create_book_via_api(
            {
                "client_book_id": "test-client-empty",
                "title": "Empty Highlights Book",
                "author": "Test Author",
            }
        )

        payload = {
            "client_book_id": "test-client-empty",
            "highlights": [],
        }

        response = await plugin_client.post("/api/v1/highlights/upload", json=payload)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["highlights_created"] == 0
        assert data["highlights_skipped"] == 0

    async def test_upload_same_text_different_datetime_is_duplicate(
        self, plugin_client: AsyncClient, create_book_via_api: CreateBookFunc
    ) -> None:
        """Test that same text at different times is considered duplicate (hash-based dedup).

        With hash-based deduplication, the hash is computed from text + book_title + author.
        Datetime is NOT part of the hash, so same text in the same book is a duplicate.
        """
        # Create the book
        await create_book_via_api(
            {
                "client_book_id": "test-client-same-text",
                "title": "Same Text Test Book",
                "author": "Test Author",
            }
        )

        payload = {
            "client_book_id": "test-client-same-text",
            "highlights": [
                {
                    "text": "Same text",
                    "datetime": "2024-01-15 14:00:00",
                },
                {
                    "text": "Same text",
                    "datetime": "2024-01-15 15:00:00",  # Different datetime, same hash
                },
            ],
        }

        response = await plugin_client.post("/api/v1/highlights/upload", json=payload)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # With hash-based dedup, only 1 is created (same text = same hash)
        assert data["highlights_created"] == 1
        assert data["highlights_skipped"] == 1

    async def test_upload_same_text_different_book_not_duplicate(
        self, plugin_client: AsyncClient, create_book_via_api: CreateBookFunc
    ) -> None:
        """Test that same text in different books is treated as duplicate.

        NEW BEHAVIOR: The content hash is computed from text only (not book metadata).
        This means same highlight text from different books will be deduplicated.
        This is the domain-centric approach that prioritizes text content.
        """
        # Create the first book
        await create_book_via_api(
            {
                "client_book_id": "test-client-first-book",
                "title": "First Book",
                "author": "Author A",
            }
        )

        # First book
        payload1 = {
            "client_book_id": "test-client-first-book",
            "highlights": [
                {
                    "text": "Same highlight text",
                    "datetime": "2024-01-15 14:00:00",
                },
            ],
        }

        response1 = await plugin_client.post("/api/v1/highlights/upload", json=payload1)
        assert response1.status_code == status.HTTP_200_OK
        assert response1.json()["highlights_created"] == 1

        # Create the second book
        await create_book_via_api(
            {
                "client_book_id": "test-client-second-book",
                "title": "Second Book",
                "author": "Author B",
            }
        )

        # Second book with same text
        payload2 = {
            "client_book_id": "test-client-second-book",
            "highlights": [
                {
                    "text": "Same highlight text",
                    "datetime": "2024-01-15 14:00:00",
                },
            ],
        }

        response2 = await plugin_client.post("/api/v1/highlights/upload", json=payload2)
        assert response2.status_code == status.HTTP_200_OK
        # Same text in different book = NOT a duplicate (scoped by book)
        # Allows highlighting the same passage in multiple books
        assert response2.json()["highlights_created"] == 1
        assert response2.json()["highlights_skipped"] == 0

    async def test_upload_invalid_payload_missing_book(self, plugin_client: AsyncClient) -> None:
        """Test upload with missing book data."""
        payload = {
            "highlights": [
                {
                    "text": "Test highlight",
                    "datetime": "2024-01-15 14:00:00",
                },
            ],
        }

        response = await plugin_client.post("/api/v1/highlights/upload", json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_upload_invalid_payload_missing_required_fields(
        self, plugin_client: AsyncClient
    ) -> None:
        """Test upload with missing required fields."""
        payload = {
            "client_book_id": "test-client-minimal",
            "highlights": [
                {
                    "text": "Test highlight",
                    # Missing datetime
                },
            ],
        }

        response = await plugin_client.post("/api/v1/highlights/upload", json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestHighlightRemovedFromDevices:
    """A highlight withheld from e-readers is untouched everywhere else."""

    async def _removed_highlight(
        self, db_session: AsyncSession, test_user: models.User
    ) -> tuple[models.Book, models.Highlight]:
        book = await create_test_book(db_session=db_session, user_id=test_user.id, title="Web Book")
        chapter = await create_test_chapter(
            db_session=db_session, book=book, name="Chapter One", chapter_number=1
        )
        highlight = await create_test_highlight(
            db_session=db_session,
            book=book,
            user_id=test_user.id,
            text="Deleted on the e-reader, kept here",
            datetime_str="2024-01-15 14:00:00",
            chapter_id=chapter.id,
            removed_from_devices_at=datetime(2024, 3, 1, tzinfo=UTC),
        )
        return book, highlight

    async def test_removed_highlight_still_appears_in_the_web_reads(
        self, client: AsyncClient, db_session: AsyncSession, test_user: models.User
    ) -> None:
        book, highlight = await self._removed_highlight(db_session, test_user)

        search = await client.get(
            f"/api/v1/books/{book.id}/highlights", params={"searchText": "e-reader"}
        )
        assert search.status_code == status.HTTP_200_OK
        found = [h for c in search.json()["chapters"] for h in c["highlights"]]
        assert [h["id"] for h in found] == [highlight.id]
        assert found[0]["text"] == "Deleted on the e-reader, kept here"

        details = await client.get(f"/api/v1/books/{book.id}")
        assert details.status_code == status.HTTP_200_OK
        listed = [h["id"] for c in details.json()["chapters"] for h in c["highlights"]]
        assert listed == [highlight.id]

    async def test_web_reads_flag_only_the_removed_highlight(
        self, client: AsyncClient, db_session: AsyncSession, test_user: models.User
    ) -> None:
        book, removed = await self._removed_highlight(db_session, test_user)
        kept = await create_test_highlight(
            db_session=db_session,
            book=book,
            user_id=test_user.id,
            text="Still on the e-reader",
            datetime_str="2024-01-16 14:00:00",
            chapter_id=removed.chapter_id,
        )

        details = await client.get(f"/api/v1/books/{book.id}")
        assert details.status_code == status.HTTP_200_OK
        by_id = {
            h["id"]: h["removed_from_devices"]
            for c in details.json()["chapters"]
            for h in c["highlights"]
        }
        assert by_id == {removed.id: True, kept.id: False}

        search = await client.get(
            f"/api/v1/books/{book.id}/highlights", params={"searchText": "e-reader"}
        )
        assert search.status_code == status.HTTP_200_OK
        searched = {
            h["id"]: h["removed_from_devices"]
            for c in search.json()["chapters"]
            for h in c["highlights"]
        }
        assert searched == {removed.id: True, kept.id: False}

    async def test_deleting_a_removed_highlight_still_soft_deletes_it(
        self, client: AsyncClient, db_session: AsyncSession, test_user: models.User
    ) -> None:
        book, highlight = await self._removed_highlight(db_session, test_user)
        before = await client.get(
            f"/api/v1/books/{book.id}/highlights", params={"searchText": "e-reader"}
        )
        assert [h["id"] for c in before.json()["chapters"] for h in c["highlights"]] == [
            highlight.id
        ]

        deletion = await client.request(
            "DELETE",
            f"/api/v1/books/{book.id}/highlight",
            json={"highlight_ids": [highlight.id]},
        )

        assert deletion.status_code == status.HTTP_200_OK
        assert deletion.json()["deleted_count"] == 1

        after = await client.get(
            f"/api/v1/books/{book.id}/highlights", params={"searchText": "e-reader"}
        )
        assert [h for c in after.json()["chapters"] for h in c["highlights"]] == []

        await db_session.refresh(highlight)
        assert highlight.deleted_at is not None
        assert highlight.removed_from_devices_at is not None


CLIENT_BOOK_ID = "client-removals"

PUSHED_HIGHLIGHTS: list[dict[str, Any]] = [
    {
        "text": "Kept on the device",
        "page": 1,
        "chapter_number": 1,
        "datetime": "2024-01-15 14:00:00",
    },
    {
        "text": "Deleted on the device",
        "page": 2,
        "chapter_number": 1,
        "datetime": "2024-01-15 14:01:00",
    },
]


async def sync(
    plugin_client: AsyncClient,
    removed_ids: list[int] | None = None,
    highlights: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Push the device's highlights, carrying its deletions in the same request."""
    payload: dict[str, Any] = {
        "client_book_id": CLIENT_BOOK_ID,
        "highlights": PUSHED_HIGHLIGHTS if highlights is None else highlights,
    }
    if removed_ids is not None:
        payload["removed_ids"] = removed_ids

    response = await plugin_client.post("/api/v1/highlights/upload", json=payload)
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


async def pulled_ids(plugin_client: AsyncClient) -> dict[str, int]:
    """What the e-reader gets back on its next pull, each text mapped to its ID."""
    response = await plugin_client.get(f"/api/v1/ereader/books/{CLIENT_BOOK_ID}/highlights")
    assert response.status_code == status.HTTP_200_OK
    return {item["text"]: item["id"] for item in response.json()["items"]}


async def pulled_texts(plugin_client: AsyncClient) -> list[str]:
    """The texts the e-reader gets back on its next pull."""
    response = await plugin_client.get(f"/api/v1/ereader/books/{CLIENT_BOOK_ID}/highlights")
    assert response.status_code == status.HTTP_200_OK
    return [item["text"] for item in response.json()["items"]]


def pushed_as_new(text: str, **overrides: str) -> dict[str, Any]:
    """The device's push of a highlight it created after its last pull."""
    original = next(h for h in PUSHED_HIGHLIGHTS if h["text"] == text)
    return {**original, "is_new": True, **overrides}


async def another_readers_copy(
    db_session: AsyncSession,
    email: str,
    text: str,
    datetime_str: str,
    removed_from_devices_at: datetime | None = None,
) -> models.Highlight:
    """The same passage in another reader's copy of the same client_book_id.

    Two readers syncing the same book share its client_book_id, so every write
    the upload does has to be scoped by user as well as by book.
    """
    other_user = models.User(email=email)
    db_session.add(other_user)
    await db_session.commit()
    await db_session.refresh(other_user)
    other_book = await create_test_book(
        db_session=db_session,
        user_id=other_user.id,
        title="Their Copy",
        client_book_id=CLIENT_BOOK_ID,
    )
    return await create_test_highlight(
        db_session=db_session,
        book=other_book,
        user_id=other_user.id,
        text=text,
        datetime_str=datetime_str,
        removed_from_devices_at=removed_from_devices_at,
    )


@pytest.fixture
async def synced_book(
    plugin_client: AsyncClient, db_session: AsyncSession, test_user: models.User
) -> tuple[models.Book, dict[str, int]]:
    """A book whose two highlights have been uploaded; maps each text to its ID."""
    book = await create_test_book(
        db_session=db_session,
        user_id=test_user.id,
        title="Sync Book",
        client_book_id=CLIENT_BOOK_ID,
    )
    await create_test_chapter(db_session, book, "Chapter One", chapter_number=1)

    assert (await sync(plugin_client))["highlights_created"] == 2

    return book, await pulled_ids(plugin_client)


class TestHighlightUploadRemovals:
    """A highlight deleted on an e-reader rides out in the next upload request."""

    async def test_removed_highlight_leaves_the_pull_but_stays_on_the_web(
        self, plugin_client: AsyncClient, synced_book: tuple[models.Book, dict[str, int]]
    ) -> None:
        book, ids = synced_book

        # The device pushes its whole set again, so the removed highlight's own
        # text arrives alongside the removal. Removals run first, so the push is
        # skipped as the duplicate it is instead of resurrecting the highlight.
        result = await sync(plugin_client, removed_ids=[ids["Deleted on the device"]])

        assert result["highlights_removed"] == 1
        assert result["highlights_created"] == 0
        assert result["highlights_skipped"] == 2
        assert await pulled_texts(plugin_client) == ["Kept on the device"]

        details = await plugin_client.get(f"/api/v1/books/{book.id}")
        assert details.status_code == status.HTTP_200_OK
        on_the_web = [h["text"] for c in details.json()["chapters"] for h in c["highlights"]]
        assert sorted(on_the_web) == ["Deleted on the device", "Kept on the device"]

    async def test_flashcards_and_bookmarks_of_a_removed_highlight_survive(
        self, plugin_client: AsyncClient, synced_book: tuple[models.Book, dict[str, int]]
    ) -> None:
        """The reason a device deletion cannot become a real delete."""
        book, ids = synced_book
        removed_id = ids["Deleted on the device"]

        flashcard = await plugin_client.post(
            f"/api/v1/highlights/{removed_id}/flashcards",
            json={"question": "Why keep it?", "answer": "The flashcard hangs off it"},
        )
        assert flashcard.status_code == status.HTTP_201_CREATED
        bookmark = await plugin_client.post(
            f"/api/v1/books/{book.id}/bookmarks", json={"highlight_id": removed_id}
        )
        assert bookmark.status_code == status.HTTP_201_CREATED

        assert (await sync(plugin_client, removed_ids=[removed_id]))["highlights_removed"] == 1

        details = await plugin_client.get(f"/api/v1/books/{book.id}")
        highlights = {h["id"]: h for c in details.json()["chapters"] for h in c["highlights"]}
        assert [f["question"] for f in highlights[removed_id]["flashcards"]] == ["Why keep it?"]

        bookmarks = await plugin_client.get(f"/api/v1/books/{book.id}/bookmarks")
        assert [b["highlight_id"] for b in bookmarks.json()["items"]] == [removed_id]

    async def test_resending_the_same_removal_changes_nothing(
        self, plugin_client: AsyncClient, synced_book: tuple[models.Book, dict[str, int]]
    ) -> None:
        """A sync interrupted after the removal is retried whole by the plugin."""
        _, ids = synced_book
        removed_ids = [ids["Deleted on the device"]]
        assert (await sync(plugin_client, removed_ids=removed_ids))["highlights_removed"] == 1

        repeat = await sync(plugin_client, removed_ids=removed_ids)

        assert repeat["highlights_removed"] == 0
        assert repeat["highlights_created"] == 0
        assert await pulled_texts(plugin_client) == ["Kept on the device"]

    async def test_unknown_and_soft_deleted_ids_are_ignored(
        self, plugin_client: AsyncClient, synced_book: tuple[models.Book, dict[str, int]]
    ) -> None:
        book, ids = synced_book
        deleted_id = ids["Deleted on the device"]
        deletion = await plugin_client.request(
            "DELETE",
            f"/api/v1/books/{book.id}/highlight",
            json={"highlight_ids": [deleted_id]},
        )
        assert deletion.json()["deleted_count"] == 1

        result = await sync(plugin_client, removed_ids=[deleted_id, 999999])

        assert result["highlights_removed"] == 0
        assert await pulled_texts(plugin_client) == ["Kept on the device"]

    async def test_another_users_highlight_is_left_alone(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        synced_book: tuple[models.Book, dict[str, int]],
    ) -> None:
        """A removal must not cross users."""
        theirs = await another_readers_copy(
            db_session, "other-removals@test.com", "Theirs", "2024-01-15 14:00:00"
        )

        result = await sync(plugin_client, removed_ids=[theirs.id])

        assert result["highlights_removed"] == 0
        await db_session.refresh(theirs)
        assert theirs.removed_from_devices_at is None

    async def test_upload_without_removed_ids_removes_nothing(
        self, plugin_client: AsyncClient, synced_book: tuple[models.Book, dict[str, int]]
    ) -> None:
        """A legacy plugin omits the field and gets today's behaviour."""
        result = await sync(plugin_client)

        assert result["highlights_removed"] == 0
        assert await pulled_texts(plugin_client) == ["Kept on the device", "Deleted on the device"]

    async def test_a_withheld_highlight_ignores_later_device_edits(
        self, plugin_client: AsyncClient, db_session: AsyncSession, test_user: models.User
    ) -> None:
        """A device that still holds the highlight cannot rewrite the web copy."""
        await create_test_book(
            db_session=db_session,
            user_id=test_user.id,
            title="Edited After Removal",
            client_book_id="client-edited",
        )
        noted = [
            {
                "text": "Noted then deleted",
                "page": 1,
                "datetime": "2025-01-01 00:00:00",
                "datetime_updated": "2025-01-01 00:00:00",
                "note": "keep this",
            }
        ]
        first = await plugin_client.post(
            "/api/v1/highlights/upload",
            json={"client_book_id": "client-edited", "highlights": noted},
        )
        assert first.json()["highlights_created"] == 1
        stored = (
            await db_session.execute(select(models.Highlight).filter_by(text="Noted then deleted"))
        ).scalar_one()

        # The same batch removes the highlight and pushes a newer, note-less edit
        # of it. Without the removal the edit would win and clear the note.
        edited = [{**noted[0], "datetime_updated": "2026-01-01 00:00:00", "note": ""}]
        second = await plugin_client.post(
            "/api/v1/highlights/upload",
            json={
                "client_book_id": "client-edited",
                "removed_ids": [stored.id],
                "highlights": edited,
            },
        )
        assert second.json()["highlights_removed"] == 1

        await db_session.refresh(stored)
        assert stored.koreader_note == "keep this"
        assert stored.koreader_updated_at == "2025-01-01 00:00:00"

    async def test_a_negative_removed_id_is_rejected(
        self, plugin_client: AsyncClient, synced_book: tuple[models.Book, dict[str, int]]
    ) -> None:
        """A malformed ID is a client error, not an unhandled domain exception."""
        response = await plugin_client.post(
            "/api/v1/highlights/upload",
            json={"client_book_id": CLIENT_BOOK_ID, "highlights": [], "removed_ids": [-1]},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert await pulled_texts(plugin_client) == ["Kept on the device", "Deleted on the device"]


class TestHighlightUploadRehighlights:
    """A passage marked again on the device brings its highlight back."""

    async def _remove_from_devices(self, plugin_client: AsyncClient, highlight_id: int) -> None:
        assert (await sync(plugin_client, removed_ids=[highlight_id]))["highlights_removed"] == 1
        assert await pulled_texts(plugin_client) == ["Kept on the device"]

    async def _delete_on_the_web(
        self, plugin_client: AsyncClient, book_id: int, ids: list[int]
    ) -> None:
        deletion = await plugin_client.request(
            "DELETE", f"/api/v1/books/{book_id}/highlight", json={"highlight_ids": ids}
        )
        assert deletion.status_code == status.HTTP_200_OK
        assert deletion.json()["deleted_count"] == len(ids)

    async def test_a_flagged_rehighlight_returns_a_removed_highlight_to_devices(
        self, plugin_client: AsyncClient, synced_book: tuple[models.Book, dict[str, int]]
    ) -> None:
        _, ids = synced_book
        await self._remove_from_devices(plugin_client, ids["Deleted on the device"])

        result = await sync(
            plugin_client,
            highlights=[PUSHED_HIGHLIGHTS[0], pushed_as_new("Deleted on the device")],
        )

        assert result["highlights_created"] == 0
        assert result["highlights_skipped"] == 2
        # The same row is back, not a second one beside it.
        assert await pulled_ids(plugin_client) == ids

    async def test_a_flagged_rehighlight_restores_a_web_deleted_highlight(
        self, plugin_client: AsyncClient, synced_book: tuple[models.Book, dict[str, int]]
    ) -> None:
        """What the web delete cascaded away stays gone; the highlight itself returns."""
        book, ids = synced_book
        deleted_id = ids["Deleted on the device"]
        flashcard = await plugin_client.post(
            f"/api/v1/highlights/{deleted_id}/flashcards",
            json={"question": "Does it come back?", "answer": "The highlight does"},
        )
        assert flashcard.status_code == status.HTTP_201_CREATED
        await self._delete_on_the_web(plugin_client, book.id, [deleted_id])

        result = await sync(plugin_client, highlights=[pushed_as_new("Deleted on the device")])

        assert result["highlights_created"] == 0
        assert await pulled_ids(plugin_client) == ids

        details = await plugin_client.get(f"/api/v1/books/{book.id}")
        on_the_web = {h["id"]: h for c in details.json()["chapters"] for h in c["highlights"]}
        assert deleted_id in on_the_web
        assert on_the_web[deleted_id]["flashcards"] == []

    async def test_a_flagged_rehighlight_takes_the_note_written_with_it(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        synced_book: tuple[models.Book, dict[str, int]],
    ) -> None:
        """Reviving happens before reconciliation, so the push's edits land on the row."""
        _, ids = synced_book
        await self._remove_from_devices(plugin_client, ids["Deleted on the device"])

        await sync(
            plugin_client,
            highlights=[
                pushed_as_new(
                    "Deleted on the device",
                    note="Marked it again",
                    datetime_updated="2026-01-01 00:00:00",
                )
            ],
        )

        stored = (
            await db_session.execute(
                select(models.Highlight).filter_by(id=ids["Deleted on the device"])
            )
        ).scalar_one()
        await db_session.refresh(stored)
        assert stored.koreader_note == "Marked it again"
        assert stored.removed_from_devices_at is None

    async def test_an_unflagged_push_leaves_a_removed_highlight_removed(
        self, plugin_client: AsyncClient, synced_book: tuple[models.Book, dict[str, int]]
    ) -> None:
        """A device that never learned the flag keeps today's behaviour."""
        _, ids = synced_book
        await self._remove_from_devices(plugin_client, ids["Deleted on the device"])

        result = await sync(plugin_client)

        assert result["highlights_created"] == 0
        assert await pulled_texts(plugin_client) == ["Kept on the device"]

    async def test_an_unflagged_push_leaves_a_web_deleted_highlight_deleted(
        self, plugin_client: AsyncClient, synced_book: tuple[models.Book, dict[str, int]]
    ) -> None:
        book, ids = synced_book
        await self._delete_on_the_web(plugin_client, book.id, [ids["Deleted on the device"]])

        result = await sync(plugin_client)

        assert result["highlights_created"] == 0
        assert await pulled_texts(plugin_client) == ["Kept on the device"]
        details = await plugin_client.get(f"/api/v1/books/{book.id}")
        on_the_web = [h["text"] for c in details.json()["chapters"] for h in c["highlights"]]
        assert on_the_web == ["Kept on the device"]

    async def test_a_flagged_push_of_a_live_highlight_only_merges_its_edits(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        synced_book: tuple[models.Book, dict[str, int]],
    ) -> None:
        """A device that lost its snapshot flags everything; nothing may double up."""
        _, ids = synced_book

        result = await sync(
            plugin_client,
            highlights=[
                pushed_as_new(
                    "Kept on the device", note="Still here", datetime_updated="2026-01-01 00:00:00"
                ),
                pushed_as_new("Deleted on the device"),
            ],
        )

        assert result["highlights_created"] == 0
        assert result["highlights_skipped"] == 2
        assert await pulled_ids(plugin_client) == ids

        stored = (
            await db_session.execute(
                select(models.Highlight).filter_by(id=ids["Kept on the device"])
            )
        ).scalar_one()
        await db_session.refresh(stored)
        assert stored.koreader_note == "Still here"

    async def test_a_flagged_rehighlight_outlives_a_removal_in_the_same_request(
        self, plugin_client: AsyncClient, synced_book: tuple[models.Book, dict[str, int]]
    ) -> None:
        """Removals run first, so re-marking the passage wins -- deterministically."""
        _, ids = synced_book

        result = await sync(
            plugin_client,
            removed_ids=[ids["Deleted on the device"]],
            highlights=[PUSHED_HIGHLIGHTS[0], pushed_as_new("Deleted on the device")],
        )

        assert result["highlights_removed"] == 1
        assert await pulled_ids(plugin_client) == ids

    async def test_another_users_removed_highlight_is_not_revived(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        synced_book: tuple[models.Book, dict[str, int]],
    ) -> None:
        """Two readers can remove the same passage; a revival must not cross users."""
        theirs = await another_readers_copy(
            db_session,
            "other-rehighlights@test.com",
            "Deleted on the device",
            "2024-01-15 14:01:00",
            removed_from_devices_at=datetime(2024, 3, 1, tzinfo=UTC),
        )

        await sync(plugin_client, highlights=[pushed_as_new("Deleted on the device")])

        await db_session.refresh(theirs)
        assert theirs.removed_from_devices_at is not None
