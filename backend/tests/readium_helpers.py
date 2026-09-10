"""Shared fixtures and helpers for the Readium endpoint tests.

The manifest and the position list are two renderings of one stored index, so
the tests for them agree about how a book gets that index and about what the
manifest links to. Both sets read the same fixture EPUBs:

- ``minimal.epub``: the plain case -- two spine chapters, a navigation document
  that is not in the spine, no author, no styling.
- ``nested_toc.epub``: a package document one directory down, a two-level
  navigation document, styles and an image among the resources, and file names
  with a space and with non-ASCII letters, which is what makes percent-encoding
  observable rather than incidental.
- ``fixed_layout.epub``: ``rendition:layout`` stated for the publication and
  overridden on one spine item.
"""

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from src import models
from src.application.web_reader.publications import ParsedPublication
from src.domain.common.value_objects import BookId
from src.infrastructure.library.services.epub_publication_parser import read_publication
from src.infrastructure.web_reader.repositories.publication_repository import PublicationRepository
from tests.conftest import create_test_book

FIXTURES = Path(__file__).parent / "fixtures"

POSITION_LIST_REL = "http://readium.org/position-list"
POSITION_LIST_MEDIA_TYPE = "application/vnd.readium.position-list+json"


def manifest_url(book_id: int) -> str:
    return f"/api/v1/readium/books/{book_id}/manifest.json"


def positions_url(book_id: int) -> str:
    return f"/api/v1/readium/books/{book_id}/positions.json"


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / f"{name}.epub").read_bytes()


def parse_fixture(name: str) -> ParsedPublication:
    return read_publication(fixture_bytes(name))


async def store_publication(
    db_session: AsyncSession,
    book: models.Book,
    publication: ParsedPublication,
    file_name: str = "book.epub",
) -> None:
    """Store a book's publication index, the way the upload does."""
    await PublicationRepository(db_session).save(BookId(book.id), file_name, publication)


async def store_fixture(db_session: AsyncSession, book: models.Book, name: str) -> None:
    await store_publication(db_session, book, parse_fixture(name), f"{name}.epub")


async def another_users_book(db_session: AsyncSession) -> models.Book:
    intruder = models.User(email="intruder@test.com")
    db_session.add(intruder)
    await db_session.commit()
    await db_session.refresh(intruder)
    return await create_test_book(
        db_session, user_id=intruder.id, title="Not Yours", author="Someone"
    )
