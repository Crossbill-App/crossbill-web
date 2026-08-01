"""Unit tests for Book entity file reference methods."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from src.domain.common.exceptions import DomainError
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.library.entities.book import Book


def _make_book(**overrides: Any) -> Book:  # noqa: ANN401
    """Create a Book with sensible defaults for testing."""
    defaults: dict[str, Any] = {
        "id": BookId(1),
        "user_id": UserId(1),
        "title": "Test Book",
        "created_at": datetime(2024, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2024, 1, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return Book(**defaults)


class TestSetFile:
    def test_generates_uuid_epub_filename_when_no_file_set(self) -> None:
        book = _make_book()

        filename = book.set_file("epub")

        assert filename.endswith(".epub")
        # Validate that the stem is a valid UUID
        stem = filename.removesuffix(".epub")
        uuid.UUID(stem)  # Raises if not valid UUID
        assert book.ebook_file == filename
        assert book.file_type == "epub"

    def test_returns_existing_filename_on_reupload(self) -> None:
        book = _make_book(ebook_file="existing-uuid.epub", file_type="epub")

        filename = book.set_file("epub")

        assert filename == "existing-uuid.epub"
        assert book.ebook_file == "existing-uuid.epub"

    def test_rejects_invalid_file_type(self) -> None:
        book = _make_book()

        with pytest.raises(DomainError, match="Invalid file type"):
            book.set_file("docx")

    def test_generates_unique_uuids(self) -> None:
        book1 = _make_book()
        book2 = _make_book()

        filename1 = book1.set_file("epub")
        filename2 = book2.set_file("epub")

        assert filename1 != filename2


class TestSetCoverFile:
    def test_generates_uuid_jpg_filename_when_no_cover_set(self) -> None:
        book = _make_book()

        filename = book.set_cover_file()

        assert filename.endswith(".jpg")
        stem = filename.removesuffix(".jpg")
        uuid.UUID(stem)
        assert book.cover_file == filename

    def test_returns_existing_filename_on_reupload(self) -> None:
        book = _make_book(cover_file="existing-uuid.jpg")

        filename = book.set_cover_file()

        assert filename == "existing-uuid.jpg"
        assert book.cover_file == "existing-uuid.jpg"


class TestSetCoverBlurhash:
    def test_sets_blurhash_on_book(self) -> None:
        book = _make_book()
        book.set_cover_blurhash("LEHV6nWB2yk8pyo0adR*.7kCMdnj")
        assert book.cover_blurhash == "LEHV6nWB2yk8pyo0adR*.7kCMdnj"

    def test_overwrites_existing_blurhash(self) -> None:
        book = _make_book(cover_blurhash="old-hash")
        book.set_cover_blurhash("new-hash")
        assert book.cover_blurhash == "new-hash"
