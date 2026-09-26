"""Tests for the plugin's single-call book upload.

The ingestion it shares with the web upload is proven in test_book_import.py; what
lives here is what the plugin route adds: the device's id and page count, and a
repeated upload answered with the book it already made.
"""

from pathlib import Path

from fastapi import status
from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src import models
from tests.conftest import create_test_book

# md5(b"Uploaded Book|"), the id the plugin would compute from the fixture EPUB.
FILE_CLIENT_BOOK_ID = "1a302e17f7c2524b5565b2b24adc7cae"
DEVICE_CLIENT_BOOK_ID = "device-computed-id"


async def upload(plugin_client: AsyncClient, content: bytes, **fields: str) -> Response:
    return await plugin_client.post(
        "/api/v1/ereader/books",
        files={"epub": ("book.epub", content, "application/epub+zip")},
        data=fields,
    )


async def book_count(db_session: AsyncSession) -> int:
    return await db_session.scalar(select(func.count()).select_from(models.Book)) or 0


class TestEreaderBookUpload:
    async def test_upload_creates_the_book_and_answers_its_metadata(
        self,
        plugin_client: AsyncClient,
        epub_bytes: bytes,
        storage_dir: Path,
    ) -> None:
        response = await upload(plugin_client, epub_bytes, client_book_id=FILE_CLIENT_BOOK_ID)

        assert response.status_code == status.HTTP_200_OK, response.text
        body = response.json()
        assert body["bookname"] == "Uploaded Book"
        assert body["has_ebook"] is True

        stored = await plugin_client.get(f"/api/v1/ereader/books/{FILE_CLIENT_BOOK_ID}")
        assert stored.json()["book_id"] == body["book_id"]
        assert stored.json()["has_ebook"] is True

    async def test_a_repeated_upload_answers_the_existing_book(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        epub_bytes: bytes,
        storage_dir: Path,
    ) -> None:
        first = await upload(plugin_client, epub_bytes, client_book_id=FILE_CLIENT_BOOK_ID)

        second = await upload(plugin_client, epub_bytes, client_book_id=FILE_CLIENT_BOOK_ID)

        assert second.status_code == status.HTTP_200_OK, second.text
        assert second.json()["book_id"] == first.json()["book_id"]
        assert second.json()["has_ebook"] is True
        assert await book_count(db_session) == 1

    async def test_the_devices_id_wins_over_the_files(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        epub_bytes: bytes,
        storage_dir: Path,
    ) -> None:
        response = await upload(plugin_client, epub_bytes, client_book_id=DEVICE_CLIENT_BOOK_ID)

        row = await db_session.get(models.Book, response.json()["book_id"])
        assert row is not None
        assert row.client_book_id == DEVICE_CLIENT_BOOK_ID
        missing = await plugin_client.get(f"/api/v1/ereader/books/{FILE_CLIENT_BOOK_ID}")
        assert missing.status_code == status.HTTP_404_NOT_FOUND

    async def test_the_page_count_is_stored(
        self,
        plugin_client: AsyncClient,
        client: AsyncClient,
        epub_bytes: bytes,
        storage_dir: Path,
    ) -> None:
        response = await upload(
            plugin_client, epub_bytes, client_book_id=FILE_CLIENT_BOOK_ID, page_count="312"
        )

        details = await client.get(f"/api/v1/books/{response.json()['book_id']}")
        assert details.json()["page_count"] == 312

    async def test_another_users_book_under_the_same_id_is_left_alone(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        epub_bytes: bytes,
        storage_dir: Path,
    ) -> None:
        stranger = models.User(email="stranger-ereader@test.com")
        db_session.add(stranger)
        await db_session.commit()
        theirs = await create_test_book(
            db_session, user_id=stranger.id, title="Theirs", client_book_id=FILE_CLIENT_BOOK_ID
        )
        theirs_id = theirs.id

        response = await upload(plugin_client, epub_bytes, client_book_id=FILE_CLIENT_BOOK_ID)

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["book_id"] != theirs_id
        await db_session.refresh(theirs)
        assert theirs.ebook_file is None


class TestRejectedEreaderUploads:
    async def test_an_invalid_epub_is_rejected(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        storage_dir: Path,
    ) -> None:
        response = await upload(plugin_client, b"garbage bytes", client_book_id="some-book")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert await book_count(db_session) == 0

    async def test_an_upload_without_a_client_book_id_is_rejected(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        epub_bytes: bytes,
        storage_dir: Path,
    ) -> None:
        response = await upload(plugin_client, epub_bytes)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert await book_count(db_session) == 0
