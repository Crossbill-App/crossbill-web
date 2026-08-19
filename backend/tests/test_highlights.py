"""Tests for highlights API endpoints."""

from pathlib import Path
from typing import Any

from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src import models
from tests.conftest import CreateBookFunc


async def resync_edited_highlight(
    client: AsyncClient,
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

    created = await client.post(
        "/api/v1/highlights/upload",
        json={"client_book_id": client_book_id, "highlights": [first]},
    )
    assert created.json()["highlights_created"] == 1

    resynced = await client.post(
        "/api/v1/highlights/upload",
        json={"client_book_id": client_book_id, "highlights": [edited]},
    )
    assert resynced.json()["highlights_created"] == 0
    assert resynced.json()["highlights_skipped"] == 1

    result = await db_session.execute(select(models.Highlight).filter_by(text=first["text"]))
    return result.scalar_one()


async def upload_then_delete_highlight(
    client: AsyncClient,
    db_session: AsyncSession,
    client_book_id: str,
    book_id: int,
    highlight: dict[str, Any],
) -> None:
    """Upload one highlight and soft-delete it again, as a reader would."""
    upload = await client.post(
        "/api/v1/highlights/upload",
        json={"client_book_id": client_book_id, "highlights": [highlight]},
    )
    assert upload.json()["highlights_created"] == 1

    result = await db_session.execute(select(models.Highlight).filter_by(text=highlight["text"]))
    deletion = await client.request(
        "DELETE",
        f"/api/v1/books/{book_id}/highlight",
        json={"highlight_ids": [result.scalar_one().id]},
    )
    assert deletion.json()["deleted_count"] == 1


class TestHighlightsUpload:
    """Test suite for highlights upload endpoint."""

    async def test_upload_highlights_success(
        self, client: AsyncClient, db_session: AsyncSession, create_book_via_api: CreateBookFunc
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

        response = await client.post("/api/v1/highlights/upload", json=payload)

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
        self, client: AsyncClient, db_session: AsyncSession, create_book_via_api: CreateBookFunc
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

        response = await client.post("/api/v1/highlights/upload", json=payload)

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
        self, client: AsyncClient, db_session: AsyncSession, create_book_via_api: CreateBookFunc
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

        response = await client.post("/api/v1/highlights/upload", json=payload)
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
        self, client: AsyncClient, db_session: AsyncSession, create_book_via_api: CreateBookFunc
    ) -> None:
        """Older plugins send no device_id; the highlight simply has no origin."""
        await create_book_via_api(
            {
                "client_book_id": "test-client-book-no-device",
                "title": "No Device Book",
                "author": "Test Author",
            }
        )

        response = await client.post(
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
        self, client: AsyncClient, db_session: AsyncSession, create_book_via_api: CreateBookFunc
    ) -> None:
        """The highlight itself is still skipped, but a later device edit lands."""
        highlight = {"text": "Same passage", "datetime": "2019-06-01 08:15:30"}

        stored = await resync_edited_highlight(
            client,
            db_session,
            create_book_via_api,
            "test-client-book-note-rewrite",
            {**highlight, "note": "first note"},
            {**highlight, "note": "edited note", "datetime_updated": "2019-06-02 09:00:00"},
        )

        assert stored.koreader_note == "edited note"
        assert stored.koreader_updated_at == "2019-06-02 09:00:00"

    async def test_reupload_ignores_an_older_note_edit(
        self, client: AsyncClient, db_session: AsyncSession, create_book_via_api: CreateBookFunc
    ) -> None:
        """A device syncing its stale copy must not undo a newer edit from elsewhere."""
        highlight = {"text": "Passage edited elsewhere", "datetime": "2019-06-01 08:15:30"}

        stored = await resync_edited_highlight(
            client,
            db_session,
            create_book_via_api,
            "test-client-book-note-stale",
            {**highlight, "note": "newer note", "datetime_updated": "2019-06-05 10:00:00"},
            {**highlight, "note": "stale note", "datetime_updated": "2019-06-02 09:00:00"},
        )

        assert stored.koreader_note == "newer note"
        assert stored.koreader_updated_at == "2019-06-05 10:00:00"

    async def test_first_edit_is_accepted_even_when_older_than_the_stored_datetime(
        self, client: AsyncClient, db_session: AsyncSession, create_book_via_api: CreateBookFunc
    ) -> None:
        """A row that never received a device edit has nothing to protect.

        Rows uploaded before notes were kept carry a server-side datetime that
        a note written on the device before that upload would never beat.
        """
        stored = await resync_edited_highlight(
            client,
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
        self, client: AsyncClient, db_session: AsyncSession, create_book_via_api: CreateBookFunc
    ) -> None:
        """Equal timestamps are not newer, so the server's copy stands."""
        highlight = {
            "text": "Passage edited at the same second",
            "datetime": "2019-06-01 08:15:30",
            "datetime_updated": "2019-06-05 10:00:00",
        }

        stored = await resync_edited_highlight(
            client,
            db_session,
            create_book_via_api,
            "test-client-book-note-tie",
            {**highlight, "note": "note on the server"},
            {**highlight, "note": "note from the device"},
        )

        assert stored.koreader_note == "note on the server"

    async def test_reupload_without_an_edit_time_compares_creation_datetimes(
        self, client: AsyncClient, db_session: AsyncSession, create_book_via_api: CreateBookFunc
    ) -> None:
        """A highlight never edited on the device carries only its creation time."""
        stored = await resync_edited_highlight(
            client,
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
        self, client: AsyncClient, db_session: AsyncSession, create_book_via_api: CreateBookFunc
    ) -> None:
        """Recolouring a highlight on the device moves it to the new style."""
        highlight = {"text": "Passage recoloured", "datetime": "2019-06-01 08:15:30"}

        stored = await resync_edited_highlight(
            client,
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
        self, client: AsyncClient, db_session: AsyncSession, create_book_via_api: CreateBookFunc
    ) -> None:
        """Deleting the note on the device clears it on the server too."""
        highlight = {"text": "Passage once annotated", "datetime": "2019-06-01 08:15:30"}

        stored = await resync_edited_highlight(
            client,
            db_session,
            create_book_via_api,
            "test-client-book-note-clearing",
            {**highlight, "note": "note to be removed"},
            {**highlight, "datetime_updated": "2019-06-02 09:00:00"},
        )

        assert stored.koreader_note is None

    async def test_reupload_leaves_soft_deleted_duplicate_alone(
        self, client: AsyncClient, db_session: AsyncSession, create_book_via_api: CreateBookFunc
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
            client,
            db_session,
            "test-client-book-note-deleted",
            book.book_id,
            {**highlight, "note": "note on a deleted highlight"},
        )

        second = await client.post(
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
        self, client: AsyncClient, db_session: AsyncSession, create_book_via_api: CreateBookFunc
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

        first = await client.post(
            "/api/v1/highlights/upload",
            json={
                "client_book_id": "test-client-book-xpoint-backfill",
                "highlights": [highlight],
            },
        )
        assert first.json()["highlights_created"] == 1

        second = await client.post(
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
        self, client: AsyncClient, db_session: AsyncSession, create_book_via_api: CreateBookFunc
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

        first = await client.post(
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

        second = await client.post(
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
        client: AsyncClient,
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
        epub_upload = await client.post(
            "/api/v1/ereader/books/test-client-book-position-backfill/epub",
            files={"epub": ("book.epub", epub_bytes, "application/epub+zip")},
        )
        assert epub_upload.status_code == status.HTTP_200_OK

        highlight = {"text": "Some content.", "datetime": "2019-06-01 08:15:30"}
        first = await client.post(
            "/api/v1/highlights/upload",
            json={
                "client_book_id": "test-client-book-position-backfill",
                "highlights": [highlight],
            },
        )
        assert first.json()["highlights_created"] == 1

        result = await db_session.execute(select(models.Highlight).filter_by(text="Some content."))
        assert result.scalar_one().position is None

        second = await client.post(
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
        self, client: AsyncClient, db_session: AsyncSession, create_book_via_api: CreateBookFunc
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
            client, db_session, "test-client-book-xpoint-deleted", book.book_id, highlight
        )

        second = await client.post(
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
        self, client: AsyncClient, db_session: AsyncSession, create_book_via_api: CreateBookFunc
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
        response1 = await client.post("/api/v1/highlights/upload", json=payload)
        assert response1.status_code == status.HTTP_200_OK
        data1 = response1.json()
        assert data1["highlights_created"] == 1
        assert data1["highlights_skipped"] == 0

        # Second upload (should skip duplicate)
        response2 = await client.post("/api/v1/highlights/upload", json=payload)
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
        self, client: AsyncClient, create_book_via_api: CreateBookFunc
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

        response1 = await client.post("/api/v1/highlights/upload", json=payload1)
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

        response2 = await client.post("/api/v1/highlights/upload", json=payload2)
        assert response2.status_code == status.HTTP_200_OK
        data2 = response2.json()
        assert data2["highlights_created"] == 1
        assert data2["highlights_skipped"] == 1

    async def test_upload_empty_highlights_list(
        self, client: AsyncClient, create_book_via_api: CreateBookFunc
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

        response = await client.post("/api/v1/highlights/upload", json=payload)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["highlights_created"] == 0
        assert data["highlights_skipped"] == 0

    async def test_upload_same_text_different_datetime_is_duplicate(
        self, client: AsyncClient, create_book_via_api: CreateBookFunc
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

        response = await client.post("/api/v1/highlights/upload", json=payload)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # With hash-based dedup, only 1 is created (same text = same hash)
        assert data["highlights_created"] == 1
        assert data["highlights_skipped"] == 1

    async def test_upload_same_text_different_book_not_duplicate(
        self, client: AsyncClient, create_book_via_api: CreateBookFunc
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

        response1 = await client.post("/api/v1/highlights/upload", json=payload1)
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

        response2 = await client.post("/api/v1/highlights/upload", json=payload2)
        assert response2.status_code == status.HTTP_200_OK
        # Same text in different book = NOT a duplicate (scoped by book)
        # Allows highlighting the same passage in multiple books
        assert response2.json()["highlights_created"] == 1
        assert response2.json()["highlights_skipped"] == 0

    async def test_upload_invalid_payload_missing_book(self, client: AsyncClient) -> None:
        """Test upload with missing book data."""
        payload = {
            "highlights": [
                {
                    "text": "Test highlight",
                    "datetime": "2024-01-15 14:00:00",
                },
            ],
        }

        response = await client.post("/api/v1/highlights/upload", json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_upload_invalid_payload_missing_required_fields(
        self, client: AsyncClient
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

        response = await client.post("/api/v1/highlights/upload", json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
