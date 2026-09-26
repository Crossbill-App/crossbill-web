"""Tests for creating a book from an EPUB uploaded in the browser."""

from collections.abc import AsyncIterator, Callable, Iterator
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient, Response
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src import models
from src.application.web_reader.publications import ParsedPublication
from src.domain.library.exceptions import InvalidEbookError
from src.infrastructure.library.repositories.chapter_repository import ChapterRepository
from src.infrastructure.library.routers import epub_upload
from src.infrastructure.library.services.epub_parser_service import EpubParserService
from src.infrastructure.web_reader.repositories import publication_repository
from src.main import app
from tests.conftest import (
    build_test_epub,
    create_test_book,
    create_test_highlight,
)
from tests.epub_builders import build_epub, container_xml

# md5(b"Uploaded Book|"), as the plugin hashes an authorless book.
UPLOADED_BOOK_ID = "1a302e17f7c2524b5565b2b24adc7cae"
NESTED_TOC_EPUB = (Path(__file__).parent / "fixtures" / "nested_toc.epub").read_bytes()
CHAPTER_ITEM = '<item id="ch1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>'
CHAPTER_SPINE = '<itemref idref="ch1"/>'
# ebooklib only finds a package document whose rootfile states its media type.
CONTAINER = container_xml(
    '<rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>'
)


async def upload(
    client: AsyncClient,
    content: bytes,
    filename: str = "book.epub",
    content_type: str = "application/epub+zip",
) -> Response:
    return await client.post("/api/v1/books/", files={"epub": (filename, content, content_type)})


def hand_built_epub(title: str | None = "Hand Built", extra_metadata: str = "") -> bytes:
    return build_epub(
        CHAPTER_ITEM,
        CHAPTER_SPINE,
        files=("chapter1.xhtml",),
        title=title,
        extra_metadata=extra_metadata,
        container=CONTAINER,
    )


def stored_files(directory: Path) -> list[Path]:
    return list(directory.iterdir()) if directory.exists() else []


async def stored_epub(db_session: AsyncSession, storage_dir: Path, book_id: int) -> bytes:
    row = await db_session.get(models.Book, book_id)
    assert row is not None
    assert row.ebook_file is not None
    return (storage_dir / row.ebook_file).read_bytes()


async def assert_chapters_without_publication(db_session: AsyncSession, book_id: int) -> None:
    chapters = await db_session.execute(select(models.Chapter).filter_by(book_id=book_id))
    publication = await db_session.execute(
        select(models.BookPublication).filter_by(book_id=book_id)
    )
    assert "Chapter 1" in [chapter.name for chapter in chapters.scalars().all()]
    assert publication.scalar_one_or_none() is None


async def library_total(client: AsyncClient) -> int:
    response = await client.get("/api/v1/books/")
    assert response.status_code == status.HTTP_200_OK
    return response.json()["total"]


@pytest.fixture
def break_chapter_storage() -> Iterator[pytest.MonkeyPatch]:
    """Fail the chapter INSERT on its foreign key, inside the repository's commit.

    Yields its own MonkeyPatch, so a test can undo the failure and upload again.
    """
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(ChapterRepository, "_resolve_parent_id", staticmethod(lambda *_: 10**9))
        yield patch


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


@pytest.fixture
async def failing_client(client: AsyncClient) -> AsyncIterator[AsyncClient]:
    """``client``'s app, answering an unhandled error with its 500 instead of raising it."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as lenient:
        yield lenient


@pytest.fixture
def covered_epub_bytes(tmp_path: Path) -> bytes:
    cover = BytesIO()
    Image.new("RGB", (60, 90), "teal").save(cover, format="PNG")
    return build_test_epub(tmp_path / "covered.epub", cover=cover.getvalue())


class TestCreateBookFromEpub:
    async def test_upload_creates_the_book_from_the_epubs_metadata(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        epub_bytes: bytes,
        storage_dir: Path,
    ) -> None:
        response = await upload(client, epub_bytes)

        assert response.status_code == status.HTTP_201_CREATED, response.text
        book = response.json()
        assert book["title"] == "Uploaded Book"
        assert book["client_book_id"] == UPLOADED_BOOK_ID
        assert book["author"] is None
        assert book["language"] == "en"

        details = await client.get(f"/api/v1/books/{book['id']}")
        assert details.status_code == status.HTTP_200_OK
        assert [chapter["name"] for chapter in details.json()["chapters"]] == ["Chapter 1"]

        assert await stored_epub(db_session, storage_dir, book["id"]) == epub_bytes
        publication = await db_session.execute(
            select(models.BookPublication).filter_by(book_id=book["id"])
        )
        row = await db_session.get(models.Book, book["id"])
        assert row is not None
        assert publication.scalar_one().file_name == row.ebook_file

    async def test_the_plugin_finds_the_uploaded_book_instead_of_creating_one(
        self,
        client: AsyncClient,
        plugin_client: AsyncClient,
        epub_bytes: bytes,
        storage_dir: Path,
    ) -> None:
        uploaded = (await upload(client, epub_bytes)).json()

        synced = await plugin_client.post(
            "/api/v1/ereader/books",
            files={"epub": ("book.epub", epub_bytes, "application/epub+zip")},
            data={"client_book_id": UPLOADED_BOOK_ID},
        )

        assert synced.json()["book_id"] == uploaded["id"]
        assert synced.json()["has_ebook"] is True
        assert await library_total(client) == 1

    async def test_creators_are_hashed_the_way_the_plugin_hashes_them(
        self, client: AsyncClient, storage_dir: Path
    ) -> None:
        content = hand_built_epub(
            extra_metadata="<dc:creator>Author One</dc:creator><dc:creator>Author Two</dc:creator>"
        )

        response = await upload(client, content)

        assert response.status_code == status.HTTP_201_CREATED, response.text
        book = response.json()
        # md5(b"Hand Built|Author One\nAuthor Two")
        assert book["client_book_id"] == "1545c535d22af08931f215e4e5fed14c"
        assert book["author"] == "Author One\nAuthor Two"

    async def test_a_missing_title_falls_back_to_the_file_name(
        self, client: AsyncClient, storage_dir: Path
    ) -> None:
        response = await upload(client, hand_built_epub(title=None), filename="My.Book.epub")

        assert response.status_code == status.HTTP_201_CREATED, response.text
        book = response.json()
        assert book["title"] == "My.Book"
        # md5(b"My.Book|")
        assert book["client_book_id"] == "fbce6496f3a9b4736e779c85cf1ddbb1"

    async def test_a_corrupt_cover_does_not_reject_the_book(
        self, client: AsyncClient, db_session: AsyncSession, storage_dir: Path
    ) -> None:
        response = await upload(client, NESTED_TOC_EPUB)

        assert response.status_code == status.HTTP_201_CREATED, response.text
        details = (await client.get(f"/api/v1/books/{response.json()['id']}")).json()
        assert details["cover_file"] is None
        assert details["chapters"] != []
        assert await stored_epub(db_session, storage_dir, details["id"]) == NESTED_TOC_EPUB

    async def test_an_overlong_title_and_author_are_cut_to_fit(
        self, client: AsyncClient, storage_dir: Path
    ) -> None:
        content = hand_built_epub(
            title="T" * 599 + "X", extra_metadata=f"<dc:creator>{'A' * 599}Z</dc:creator>"
        )

        response = await upload(client, content)

        assert response.status_code == status.HTTP_201_CREATED, response.text
        book = response.json()
        assert book["title"] == "T" * 500
        assert book["author"] == "A" * 500
        details = (await client.get(f"/api/v1/books/{book['id']}")).json()
        assert (details["title"], details["author"]) == (book["title"], book["author"])


class TestExistingBooks:
    async def test_uploading_the_same_epub_twice_is_a_conflict(
        self, client: AsyncClient, epub_bytes: bytes, storage_dir: Path
    ) -> None:
        first = await upload(client, epub_bytes)
        assert first.status_code == status.HTTP_201_CREATED

        second = await upload(client, epub_bytes)

        assert second.status_code == status.HTTP_409_CONFLICT
        assert second.json()["error"] == "conflict"
        assert await library_total(client) == 1
        assert len(stored_files(storage_dir)) == 1

    async def test_an_epub_is_attached_to_a_book_that_has_none(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: models.User,
        epub_bytes: bytes,
        storage_dir: Path,
    ) -> None:
        synced = await create_test_book(
            db_session, user_id=test_user.id, title="Synced", client_book_id=UPLOADED_BOOK_ID
        )
        await create_test_highlight(
            db_session,
            book=synced,
            user_id=test_user.id,
            text="Kept highlight",
            datetime_str="2024-01-15 14:30:22",
        )
        book_id = synced.id

        response = await upload(client, epub_bytes)

        assert response.status_code == status.HTTP_201_CREATED, response.text
        assert response.json()["id"] == book_id
        assert response.json()["title"] == "Synced"
        details = (await client.get(f"/api/v1/books/{book_id}")).json()
        assert details["highlight_count"] == 1
        assert await library_total(client) == 1
        assert await stored_epub(db_session, storage_dir, book_id) == epub_bytes

    @pytest.mark.parametrize("theirs_has_a_file", [False, True])
    async def test_another_users_copy_of_the_book_is_left_alone(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        epub_bytes: bytes,
        storage_dir: Path,
        theirs_has_a_file: bool,
    ) -> None:
        stranger = models.User(email="stranger@test.com")
        db_session.add(stranger)
        await db_session.commit()
        theirs = await create_test_book(
            db_session, user_id=stranger.id, title="Theirs", client_book_id=UPLOADED_BOOK_ID
        )
        theirs.ebook_file = "theirs.epub" if theirs_has_a_file else None
        await db_session.commit()
        theirs_id = theirs.id

        response = await upload(client, epub_bytes)

        assert response.status_code == status.HTTP_201_CREATED, response.text
        mine = response.json()
        assert mine["id"] != theirs_id
        # The details route only finds the caller's own books.
        assert (await client.get(f"/api/v1/books/{mine['id']}")).status_code == 200
        await db_session.refresh(theirs)
        assert theirs.ebook_file == ("theirs.epub" if theirs_has_a_file else None)

    async def test_a_failed_ingestion_leaves_a_synced_book_without_a_file(
        self,
        failing_client: AsyncClient,
        db_session: AsyncSession,
        test_user: models.User,
        covered_epub_bytes: bytes,
        storage_dir: Path,
        break_chapter_storage: pytest.MonkeyPatch,
    ) -> None:
        synced = await create_test_book(
            db_session, user_id=test_user.id, title="Synced", client_book_id=UPLOADED_BOOK_ID
        )
        book_id = synced.id

        response = await upload(failing_client, covered_epub_bytes)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        details = await failing_client.get(f"/api/v1/books/{book_id}")
        assert details.status_code == status.HTTP_200_OK
        row = await db_session.execute(
            select(models.Book.ebook_file, models.Book.cover_file).filter_by(id=book_id)
        )
        assert row.one() == (None, None)
        assert stored_files(storage_dir) == []
        assert stored_files(storage_dir.parent / "covers") == []

        break_chapter_storage.undo()
        retry = await upload(failing_client, covered_epub_bytes)
        assert retry.status_code == status.HTTP_201_CREATED, retry.text
        assert retry.json()["id"] == book_id


class TestUploadDerivesPublication:
    async def test_upload_succeeds_when_the_publication_cannot_be_parsed(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        epub_bytes: bytes,
        storage_dir: Path,
        break_publication_parsing: Callable[[], None],
    ) -> None:
        break_publication_parsing()

        response = await upload(client, epub_bytes)

        assert response.status_code == status.HTTP_201_CREATED, response.text
        await assert_chapters_without_publication(db_session, response.json()["id"])

    async def test_upload_succeeds_when_the_index_cannot_be_stored(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        epub_bytes: bytes,
        storage_dir: Path,
        break_publication_storage: None,
    ) -> None:
        response = await upload(client, epub_bytes)

        assert response.status_code == status.HTTP_201_CREATED, response.text
        # Chapters are synced after the derivation, on the same session: they
        # are what a failure left needing a rollback would take down with it.
        await assert_chapters_without_publication(db_session, response.json()["id"])

    async def test_deleting_the_book_cascades_the_index_away(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        epub_bytes: bytes,
        storage_dir: Path,
    ) -> None:
        # No application code deletes the row on book deletion: the FK cascade does.
        book_id = (await upload(client, epub_bytes)).json()["id"]

        response = await client.delete(f"/api/v1/books/{book_id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        result = await db_session.execute(select(models.BookPublication).filter_by(book_id=book_id))
        assert result.scalar_one_or_none() is None


class TestRejectedUploads:
    async def test_a_file_that_is_not_an_epub_is_rejected(
        self, client: AsyncClient, storage_dir: Path
    ) -> None:
        response = await upload(client, b"not a zip")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["error"] == "bad_request"
        assert await library_total(client) == 0
        assert stored_files(storage_dir) == []

    async def test_an_octet_stream_named_epub_is_accepted(
        self, client: AsyncClient, epub_bytes: bytes, storage_dir: Path
    ) -> None:
        response = await upload(client, epub_bytes, content_type="application/octet-stream")

        assert response.status_code == status.HTTP_201_CREATED, response.text
        assert response.json()["title"] == "Uploaded Book"

    async def test_a_wrong_type_and_name_is_rejected(
        self, client: AsyncClient, epub_bytes: bytes, storage_dir: Path
    ) -> None:
        response = await upload(
            client, epub_bytes, filename="book.pdf", content_type="application/pdf"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert await library_total(client) == 0

    async def test_an_oversized_file_is_rejected(
        self,
        client: AsyncClient,
        epub_bytes: bytes,
        storage_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(epub_upload, "MAX_EBOOK_SIZE", len(epub_bytes) - 1)

        response = await upload(client, epub_bytes)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["message"].startswith("Invalid EPUB: file too large")
        assert await library_total(client) == 0
        assert stored_files(storage_dir) == []

    async def test_a_failed_ingestion_leaves_no_book_behind(
        self,
        failing_client: AsyncClient,
        covered_epub_bytes: bytes,
        storage_dir: Path,
        break_chapter_storage: pytest.MonkeyPatch,
    ) -> None:
        response = await upload(failing_client, covered_epub_bytes)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert await library_total(failing_client) == 0
        assert stored_files(storage_dir) == []
        assert stored_files(storage_dir.parent / "covers") == []
