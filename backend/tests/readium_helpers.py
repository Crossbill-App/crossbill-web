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

``build_epub`` assembles adversarial publications by hand, for the shapes no
fixture on disk has.
"""

from pathlib import Path

from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src import models
from src.application.web_reader.publications import ParsedPublication
from src.domain.common.value_objects import BookId
from src.infrastructure.identity.services.token_service import create_access_token
from src.infrastructure.library.services.epub_publication_parser import read_publication
from src.infrastructure.web_reader.repositories.publication_repository import PublicationRepository
from src.infrastructure.web_reader.services.publication_token_service import (
    PUBLICATION_COOKIE_NAME,
)
from tests.conftest import create_test_book
from tests.epub_builders import NAV_ITEM, nav_document
from tests.epub_builders import build_epub as _build_epub

FIXTURES = Path(__file__).parent / "fixtures"

POSITION_LIST_REL = "http://readium.org/position-list"
POSITION_LIST_MEDIA_TYPE = "application/vnd.readium.position-list+json"

# httpx's jar stores a single-label host with ".local" appended, so a cookie
# planted under plain "test" is silently never sent -- and a test asserting a
# refusal would be asserting that nothing was offered.
COOKIE_DOMAIN = "test.local"


def manifest_url(book_id: int) -> str:
    return f"/api/v1/readium/books/{book_id}/manifest.json"


def positions_url(book_id: int) -> str:
    return f"/api/v1/readium/books/{book_id}/positions.json"


def session_url(book_id: int) -> str:
    return f"/api/v1/readium/books/{book_id}/session"


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


def build_epub(
    manifest_items: str, spine: str, nav_links: str, files: tuple[str, ...] = ()
) -> bytes:
    """Assemble an EPUB by hand, with the navigation document its manifest names."""
    return _build_epub(
        manifest_items=f"{NAV_ITEM}{manifest_items}",
        spine=spine,
        files=files,
        documents={"nav.xhtml": nav_document(nav_links)},
    )


# A publication whose one spine document is really named `chapter%20one.xhtml`
# -- a literal percent sign in the file name, which the OPF therefore writes as
# `chapter%2520one.xhtml`.
LITERAL_PERCENT_EPUB = build_epub(
    manifest_items=(
        '<item id="c1" href="chapter%2520one.xhtml" media-type="application/xhtml+xml"/>'
    ),
    spine='<itemref idref="c1"/>',
    nav_links='<li><a href="chapter%2520one.xhtml">Chapter One</a></li>',
    files=("chapter%20one.xhtml",),
)


async def another_users_book(db_session: AsyncSession) -> models.Book:
    intruder = models.User(email="intruder@test.com")
    db_session.add(intruder)
    await db_session.commit()
    await db_session.refresh(intruder)
    return await create_test_book(
        db_session, user_id=intruder.id, title="Not Yours", author="Someone"
    )


async def another_users_indexed_book(db_session: AsyncSession) -> models.Book:
    """Another user's book with a publication stored, so only ownership can hide it."""
    theirs = await another_users_book(db_session)
    await store_fixture(db_session, theirs, "minimal")
    return theirs


async def start_session(browser_client: AsyncClient, user_id: int, book_id: int) -> Response:
    return await browser_client.post(
        session_url(book_id),
        headers={"Authorization": f"Bearer {create_access_token(user_id)}"},
    )


def present(browser_client: AsyncClient, token: str) -> None:
    """Put ``token`` in the jar under the whole API, replacing whatever is there.

    The path is deliberately wider than the server's: what is under test is what
    the server makes of a cookie presented where it does not belong, and a jar
    honouring the cookie's own path would answer by never sending it.
    """
    browser_client.cookies.clear()
    browser_client.cookies.set(PUBLICATION_COOKIE_NAME, token, domain=COOKIE_DOMAIN, path="/")


async def hold_publication_cookie(
    browser_client: AsyncClient, db_session: AsyncSession, user_id: int, book: models.Book
) -> None:
    """Give a browser client this book's publication cookie and no other credential."""
    await store_fixture(db_session, book, "minimal")
    minted = await start_session(browser_client, user_id, book.id)
    present(browser_client, minted.cookies[PUBLICATION_COOKIE_NAME])
