"""Tests for the ereader EPUB upload endpoint (multipart form parsing)."""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src import models
from src.application.web_reader.publications import ParsedPublication
from src.domain.library.exceptions import InvalidEbookError
from src.infrastructure.library.services.epub_parser_service import EpubParserService
from src.infrastructure.library.services.epub_publication_parser import read_publication
from src.infrastructure.web_reader.repositories import publication_repository
from tests.conftest import create_test_book

CLIENT_BOOK_ID = "test-client-book-1"
OTHER_EPUB = (Path(__file__).parent / "fixtures" / "minimal.epub").read_bytes()


@pytest.fixture
async def ereader_book(db_session: AsyncSession, test_user: models.User) -> models.Book:
    return await create_test_book(
        db_session=db_session,
        user_id=test_user.id,
        title="Ereader Book",
        client_book_id=CLIENT_BOOK_ID,
    )


class _UnparseablePublication(EpubParserService):
    """An EPUB parser whose publication pass fails and whose other passes do not."""

    def parse_publication(self, epub_content: bytes) -> ParsedPublication:
        raise InvalidEbookError("package document unreadable", ebook_type="EPUB")


@pytest.fixture
def break_publication_parsing() -> Iterator[Callable[[], None]]:
    """Yields the switch that makes ``parse_publication`` -- and only it -- start failing."""
    from src.core import container  # noqa: PLC0415

    def start_failing() -> None:
        container.shared.epub_parser_service.override(_UnparseablePublication())

    yield start_failing
    container.shared.epub_parser_service.reset_override()


@pytest.fixture
def break_publication_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    """Makes the real repository fail where it hurts: inside its commit.

    A stub raising before it touches the session would not reproduce the
    failure that matters -- the one that leaves the session needing a rollback.
    """

    def unserialisable(publication: ParsedPublication) -> dict[str, object]:
        return {"reading_order": object()}

    monkeypatch.setattr(publication_repository, "publication_to_json", unserialisable)


async def upload_epub(client: AsyncClient, content: bytes) -> None:
    response = await client.post(
        f"/api/v1/ereader/books/{CLIENT_BOOK_ID}/epub",
        files={"epub": ("book.epub", content, "application/epub+zip")},
    )
    assert response.status_code == status.HTTP_200_OK


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
            "/api/v1/highlights/sync",
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


class TestUploadDerivesPublication:
    async def test_upload_stores_the_publication_index(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        ereader_book: models.Book,
        epub_bytes: bytes,
        storage_dir: Path,
    ) -> None:
        expected = read_publication(epub_bytes)

        await upload_epub(plugin_client, epub_bytes)

        await db_session.refresh(ereader_book)
        result = await db_session.execute(
            select(models.BookPublication).filter_by(book_id=ereader_book.id)
        )
        row = result.scalar_one()
        assert row.file_name == ereader_book.ebook_file
        assert row.content_hash == expected.content_hash
        assert len(row.publication["reading_order"]) == len(expected.reading_order)

    async def test_re_upload_replaces_the_index_with_the_new_files(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        ereader_book: models.Book,
        epub_bytes: bytes,
        storage_dir: Path,
    ) -> None:
        replacement = read_publication(OTHER_EPUB)
        assert replacement.content_hash != read_publication(epub_bytes).content_hash

        await upload_epub(plugin_client, epub_bytes)
        await upload_epub(plugin_client, OTHER_EPUB)

        count = await db_session.scalar(select(func.count()).select_from(models.BookPublication))
        result = await db_session.execute(
            select(models.BookPublication).filter_by(book_id=ereader_book.id)
        )
        assert count == 1
        assert result.scalar_one().content_hash == replacement.content_hash

    async def test_upload_succeeds_when_the_publication_cannot_be_parsed(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        ereader_book: models.Book,
        epub_bytes: bytes,
        storage_dir: Path,
        break_publication_parsing: Callable[[], None],
    ) -> None:
        break_publication_parsing()

        await upload_epub(plugin_client, epub_bytes)

        chapters = await db_session.execute(
            select(models.Chapter).filter_by(book_id=ereader_book.id)
        )
        publication = await db_session.execute(
            select(models.BookPublication).filter_by(book_id=ereader_book.id)
        )
        assert "Chapter 1" in [chapter.name for chapter in chapters.scalars().all()]
        assert publication.scalar_one_or_none() is None

    async def test_upload_succeeds_when_the_index_cannot_be_stored(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        ereader_book: models.Book,
        epub_bytes: bytes,
        storage_dir: Path,
        break_publication_storage: None,
    ) -> None:
        # Read before the upload: the rollback under test expires this object,
        # and reloading it would be a sync lazy load inside an async session.
        book_id = ereader_book.id

        await upload_epub(plugin_client, epub_bytes)

        chapters = await db_session.execute(select(models.Chapter).filter_by(book_id=book_id))
        publication = await db_session.execute(
            select(models.BookPublication).filter_by(book_id=book_id)
        )
        # Chapters are synced after the derivation, on the same session: they
        # are what a failure left needing a rollback would take down with it.
        assert "Chapter 1" in [chapter.name for chapter in chapters.scalars().all()]
        assert publication.scalar_one_or_none() is None

    async def test_a_failed_parse_drops_the_index_of_the_previous_file(
        self,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        ereader_book: models.Book,
        epub_bytes: bytes,
        storage_dir: Path,
        break_publication_parsing: Callable[[], None],
    ) -> None:
        await upload_epub(plugin_client, epub_bytes)
        break_publication_parsing()

        await upload_epub(plugin_client, OTHER_EPUB)

        result = await db_session.execute(
            select(models.BookPublication).filter_by(book_id=ereader_book.id)
        )
        assert result.scalar_one_or_none() is None

    async def test_deleting_the_book_cascades_the_index_away(
        self,
        client: AsyncClient,
        plugin_client: AsyncClient,
        db_session: AsyncSession,
        ereader_book: models.Book,
        epub_bytes: bytes,
        storage_dir: Path,
    ) -> None:
        # No application code deletes the row on book deletion: the FK cascade does.
        await upload_epub(plugin_client, epub_bytes)
        stored = await db_session.execute(
            select(models.BookPublication).filter_by(book_id=ereader_book.id)
        )
        assert stored.scalar_one_or_none() is not None

        response = await client.delete(f"/api/v1/books/{ereader_book.id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        result = await db_session.execute(
            select(models.BookPublication).filter_by(book_id=ereader_book.id)
        )
        assert result.scalar_one_or_none() is None
