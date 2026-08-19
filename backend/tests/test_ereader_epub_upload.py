"""Tests for the ereader EPUB upload endpoint (multipart form parsing)."""

from pathlib import Path

import pytest
from ebooklib import epub
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src import models
from src.infrastructure.library.repositories import file_repository
from tests.conftest import create_test_book

CLIENT_BOOK_ID = "test-client-book-1"


def _build_epub(path: Path) -> bytes:
    book = epub.EpubBook()
    book.set_identifier("upload-test-epub")
    book.set_title("Uploaded Book")
    book.set_language("en")

    chapter = epub.EpubHtml(title="Chapter 1", file_name="chap01.xhtml", lang="en")
    chapter.content = "<h1>Chapter 1</h1><p>Some content.</p>"
    book.add_item(chapter)
    book.toc = [epub.Link("chap01.xhtml", "Chapter 1", "chap01")]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", chapter]

    epub.write_epub(str(path), book)
    return path.read_bytes()


@pytest.fixture
def epub_bytes(tmp_path: Path) -> bytes:
    return _build_epub(tmp_path / "upload.epub")


@pytest.fixture
def storage_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    epubs_dir = tmp_path / "epubs"
    monkeypatch.setattr(file_repository, "EPUBS_DIR", epubs_dir)
    monkeypatch.setattr(file_repository, "BOOK_COVERS_DIR", tmp_path / "covers")
    return epubs_dir


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
        client: AsyncClient,
        db_session: AsyncSession,
        ereader_book: models.Book,
        epub_bytes: bytes,
        storage_dir: Path,
    ) -> None:
        response = await client.post(
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
        client: AsyncClient,
        db_session: AsyncSession,
        ereader_book: models.Book,
        epub_bytes: bytes,
        storage_dir: Path,
    ) -> None:
        response = await client.post(
            f"/api/v1/ereader/books/{CLIENT_BOOK_ID}/epub",
            files={"epub": ("book.epub", epub_bytes, "application/epub+zip")},
        )

        assert response.status_code == status.HTTP_200_OK
        result = await db_session.execute(select(models.Chapter).filter_by(book_id=ereader_book.id))
        chapter_names = [chapter.name for chapter in result.scalars().all()]
        assert "Chapter 1" in chapter_names

    async def test_upload_rejects_wrong_content_type(
        self,
        client: AsyncClient,
        ereader_book: models.Book,
    ) -> None:
        response = await client.post(
            f"/api/v1/ereader/books/{CLIENT_BOOK_ID}/epub",
            files={"epub": ("book.txt", b"not an epub", "text/plain")},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_upload_rejects_invalid_epub_content(
        self,
        client: AsyncClient,
        ereader_book: models.Book,
        storage_dir: Path,
    ) -> None:
        response = await client.post(
            f"/api/v1/ereader/books/{CLIENT_BOOK_ID}/epub",
            files={"epub": ("book.epub", b"garbage bytes", "application/epub+zip")},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_upload_unknown_client_book_id_returns_404(
        self,
        client: AsyncClient,
        epub_bytes: bytes,
        storage_dir: Path,
    ) -> None:
        response = await client.post(
            "/api/v1/ereader/books/no-such-book/epub",
            files={"epub": ("book.epub", epub_bytes, "application/epub+zip")},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_upload_backfills_positions_of_existing_highlights(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        ereader_book: models.Book,
        epub_bytes: bytes,
        storage_dir: Path,
    ) -> None:
        upload = await client.post(
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

        response = await client.post(
            f"/api/v1/ereader/books/{CLIENT_BOOK_ID}/epub",
            files={"epub": ("book.epub", epub_bytes, "application/epub+zip")},
        )
        assert response.status_code == status.HTTP_200_OK

        result = await db_session.execute(
            select(models.Highlight).filter_by(book_id=ereader_book.id)
        )
        highlight = result.scalar_one()
        assert highlight.position is not None
