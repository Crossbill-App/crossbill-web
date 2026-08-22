"""Tests for the ereader EPUB upload endpoint (multipart form parsing)."""

from pathlib import Path

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src import models
from tests.conftest import create_test_book

CLIENT_BOOK_ID = "test-client-book-1"


@pytest.fixture
async def ereader_book(db_session: AsyncSession, test_user: models.User) -> models.Book:
    return await create_test_book(
        db_session=db_session,
        user_id=test_user.id,
        title="Ereader Book",
        client_book_id=CLIENT_BOOK_ID,
    )


class TestEpubUpload:
    async def test_upload_success_stores_file(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        ereader_book: models.Book,
        epub_bytes: bytes,
        storage_dir: Path,
    ) -> None:
        response = await plugin_client.post(
            f"/api/v1/ereader/books/{CLIENT_BOOK_ID}/epub",
            files={"epub": ("book.epub", epub_bytes, "application/epub+zip")},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["success"] is True

        await db_session.refresh(ereader_book)
        assert ereader_book.ebook_file is not None
        assert (storage_dir / ereader_book.ebook_file).read_bytes() == epub_bytes

    async def test_upload_creates_chapters_from_toc(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        ereader_book: models.Book,
        epub_bytes: bytes,
        storage_dir: Path,
    ) -> None:
        response = await plugin_client.post(
            f"/api/v1/ereader/books/{CLIENT_BOOK_ID}/epub",
            files={"epub": ("book.epub", epub_bytes, "application/epub+zip")},
        )

        assert response.status_code == status.HTTP_200_OK
        result = await db_session.execute(select(models.Chapter).filter_by(book_id=ereader_book.id))
        chapter_names = [chapter.name for chapter in result.scalars().all()]
        assert "Chapter 1" in chapter_names

    async def test_upload_rejects_wrong_content_type(
        self,
        plugin_client: AsyncClient,
        ereader_book: models.Book,
    ) -> None:
        response = await plugin_client.post(
            f"/api/v1/ereader/books/{CLIENT_BOOK_ID}/epub",
            files={"epub": ("book.txt", b"not an epub", "text/plain")},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_upload_rejects_invalid_epub_content(
        self,
        plugin_client: AsyncClient,
        ereader_book: models.Book,
        storage_dir: Path,
    ) -> None:
        response = await plugin_client.post(
            f"/api/v1/ereader/books/{CLIENT_BOOK_ID}/epub",
            files={"epub": ("book.epub", b"garbage bytes", "application/epub+zip")},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_upload_unknown_client_book_id_returns_404(
        self,
        plugin_client: AsyncClient,
        epub_bytes: bytes,
        storage_dir: Path,
    ) -> None:
        response = await plugin_client.post(
            "/api/v1/ereader/books/no-such-book/epub",
            files={"epub": ("book.epub", epub_bytes, "application/epub+zip")},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_upload_backfills_positions_of_existing_highlights(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        ereader_book: models.Book,
        epub_bytes: bytes,
        storage_dir: Path,
    ) -> None:
        upload = await plugin_client.post(
            "/api/v1/highlights/upload",
            json={
                "client_book_id": CLIENT_BOOK_ID,
                "highlights": [
                    {
                        "text": "Some content.",
                        "datetime": "2024-01-15 14:30:22",
                        "start_xpoint": "/body/DocFragment[2]/body/p[1]/text().0",
                        "end_xpoint": "/body/DocFragment[2]/body/p[1]/text().13",
                    }
                ],
            },
        )
        assert upload.json()["highlights_created"] == 1

        response = await plugin_client.post(
            f"/api/v1/ereader/books/{CLIENT_BOOK_ID}/epub",
            files={"epub": ("book.epub", epub_bytes, "application/epub+zip")},
        )
        assert response.status_code == status.HTTP_200_OK

        result = await db_session.execute(
            select(models.Highlight).filter_by(book_id=ereader_book.id)
        )
        highlight = result.scalar_one()
        assert highlight.position is not None
