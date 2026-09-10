"""Tests for the publication-resource read model."""

import zipfile
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.web_reader.publications import (
    ParsedPublication,
    PublicationMetadata,
    PublicationResource,
)
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.library.exceptions import EbookFileNotFoundError, InvalidEbookError
from src.domain.web_reader.exceptions import PublicationResourceNotFoundError
from src.infrastructure.library.repositories.file_repository import FileRepository
from src.infrastructure.web_reader.queries.publication_resource_query import (
    PublicationResourceQuery,
)
from src.models import Book
from tests.conftest import create_test_book
from tests.readium_helpers import (
    another_users_book,
    fixture_bytes,
    parse_fixture,
    store_publication,
)

DEFAULT_USER_ID = 1
FILE_NAME = "nested_toc.epub"
XHTML = "application/xhtml+xml"


@pytest.fixture
def query(db_session: AsyncSession) -> PublicationResourceQuery:
    return PublicationResourceQuery(db=db_session, file_repository=FileRepository())


@pytest.fixture
async def nested_toc_book(db_session: AsyncSession, test_book: Book, storage_dir: Path) -> Book:
    await store_nested_toc(db_session, test_book, storage_dir)
    return test_book


async def store_nested_toc(db_session: AsyncSession, book: Book, storage_dir: Path) -> None:
    await store_publication(db_session, book, parse_fixture("nested_toc"), FILE_NAME)
    write_epub(storage_dir, fixture_bytes("nested_toc"))


def member_of(name: str, path: str) -> bytes:
    with zipfile.ZipFile(BytesIO(fixture_bytes(name))) as archive:
        return archive.read(path)


def write_epub(storage_dir: Path, content: bytes) -> None:
    storage_dir.mkdir(parents=True, exist_ok=True)
    (storage_dir / FILE_NAME).write_bytes(content)


def archive_of(members: dict[str, bytes]) -> bytes:
    out = BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        for name, body in members.items():
            archive.writestr(name, body)
    return out.getvalue()


def publication_of(*resources: PublicationResource) -> ParsedPublication:
    """An index written by hand, for archives no fixture EPUB describes."""
    return ParsedPublication(
        metadata=PublicationMetadata(
            title="Hand Built", author=None, language="en", identifier=None
        ),
        reading_order=resources,
        resources=(),
        toc=(),
        content_hash="0" * 64,
    )


async def test_reading_order_document_is_served_verbatim(
    query: PublicationResourceQuery, nested_toc_book: Book
) -> None:
    view = await query.get_publication_resource(
        BookId(nested_toc_book.id), UserId(DEFAULT_USER_ID), "EPUB/text/chapter 1.xhtml"
    )

    assert view is not None
    assert view.content == member_of("nested_toc", "EPUB/text/chapter 1.xhtml")
    assert view.media_type == "application/xhtml+xml"


async def test_supporting_resource_is_served(
    query: PublicationResourceQuery, nested_toc_book: Book
) -> None:
    view = await query.get_publication_resource(
        BookId(nested_toc_book.id), UserId(DEFAULT_USER_ID), "EPUB/styles/main.css"
    )

    assert view is not None
    assert view.content == member_of("nested_toc", "EPUB/styles/main.css")
    assert view.media_type == "text/css"


async def test_member_with_non_ascii_name_is_reached_by_its_decoded_path(
    query: PublicationResourceQuery, nested_toc_book: Book
) -> None:
    view = await query.get_publication_resource(
        BookId(nested_toc_book.id), UserId(DEFAULT_USER_ID), "EPUB/text/luku-ääni.xhtml"
    )

    assert view is not None
    assert view.content == member_of("nested_toc", "EPUB/text/luku-ääni.xhtml")


@pytest.mark.parametrize(
    "path",
    ["EPUB/package.opf", "META-INF/container.xml", "mimetype", "../../etc/passwd"],
)
async def test_path_the_publication_does_not_list_is_not_found(
    query: PublicationResourceQuery, nested_toc_book: Book, path: str
) -> None:
    with pytest.raises(PublicationResourceNotFoundError):
        await query.get_publication_resource(
            BookId(nested_toc_book.id), UserId(DEFAULT_USER_ID), path
        )


async def test_listed_resource_the_archive_lacks_is_not_found(
    query: PublicationResourceQuery,
    db_session: AsyncSession,
    test_book: Book,
    storage_dir: Path,
) -> None:
    publication = parse_fixture("minimal")
    missing = PublicationResource(
        href="OEBPS/promised.xhtml", media_type="application/xhtml+xml", size=10
    )
    await store_publication(
        db_session,
        test_book,
        replace(publication, resources=(*publication.resources, missing)),
        FILE_NAME,
    )
    write_epub(storage_dir, fixture_bytes("minimal"))

    with pytest.raises(PublicationResourceNotFoundError):
        await query.get_publication_resource(
            BookId(test_book.id), UserId(DEFAULT_USER_ID), "OEBPS/promised.xhtml"
        )


async def test_another_users_book_reads_as_absent(
    query: PublicationResourceQuery, db_session: AsyncSession, storage_dir: Path
) -> None:
    book = await another_users_book(db_session)
    await store_nested_toc(db_session, book, storage_dir)

    view = await query.get_publication_resource(
        BookId(book.id), UserId(DEFAULT_USER_ID), "EPUB/text/chapter 1.xhtml"
    )

    assert view is None


async def test_member_whose_name_contains_a_percent_sign_round_trips(
    query: PublicationResourceQuery,
    db_session: AsyncSession,
    test_book: Book,
    storage_dir: Path,
) -> None:
    member = "chapter%20one.xhtml"
    body = b"<html><body>Literal percent.</body></html>"
    await store_publication(
        db_session,
        test_book,
        publication_of(PublicationResource(href=quote(member), media_type=XHTML, size=len(body))),
        FILE_NAME,
    )
    write_epub(storage_dir, archive_of({member: body}))

    view = await query.get_publication_resource(
        BookId(test_book.id), UserId(DEFAULT_USER_ID), member
    )

    assert view is not None
    assert view.content == body


async def test_the_requested_books_index_is_the_one_read(
    query: PublicationResourceQuery,
    db_session: AsyncSession,
    test_book: Book,
    nested_toc_book: Book,
    storage_dir: Path,
) -> None:
    other = await create_test_book(
        db_session, user_id=DEFAULT_USER_ID, title="Minimal", author="Nobody"
    )
    await store_publication(db_session, other, parse_fixture("minimal"), "minimal.epub")
    (storage_dir / "minimal.epub").write_bytes(fixture_bytes("minimal"))

    view = await query.get_publication_resource(
        BookId(other.id), UserId(DEFAULT_USER_ID), "OEBPS/chapter1.xhtml"
    )

    assert view is not None
    assert view.content == member_of("minimal", "OEBPS/chapter1.xhtml")


async def test_stored_file_that_is_not_an_archive_is_an_invalid_ebook(
    query: PublicationResourceQuery,
    db_session: AsyncSession,
    test_book: Book,
    storage_dir: Path,
) -> None:
    await store_publication(db_session, test_book, parse_fixture("nested_toc"), FILE_NAME)
    write_epub(storage_dir, b"not a zip at all")

    with pytest.raises(InvalidEbookError):
        await query.get_publication_resource(
            BookId(test_book.id), UserId(DEFAULT_USER_ID), "EPUB/text/chapter 1.xhtml"
        )


async def test_index_whose_epub_is_not_stored_raises(
    query: PublicationResourceQuery,
    db_session: AsyncSession,
    test_book: Book,
    storage_dir: Path,
) -> None:
    await store_publication(db_session, test_book, parse_fixture("nested_toc"), FILE_NAME)

    with pytest.raises(EbookFileNotFoundError):
        await query.get_publication_resource(
            BookId(test_book.id), UserId(DEFAULT_USER_ID), "EPUB/text/chapter 1.xhtml"
        )
