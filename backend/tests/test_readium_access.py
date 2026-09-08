"""Who may read a publication, asserted once for every endpoint that serves one.

The manifest (M1.1), a resource (M1.2) and the position list (M1.3) are three
views of one book, reached through one dependency and one stored-EPUB lookup, so
the rules about *who may look* are not three rules -- they are one rule with
three front doors. Asserting it per endpoint meant three copies that could drift
apart silently, and drift here is the worst realistic bug in the application: an
endpoint that forgets the ``user_id`` filter serves one user's library to
another.

So the endpoints are the parameter. A fourth web reader route added without a
row in :data:`READIUM_ENDPOINTS` gets none of this coverage, which is the one
way this can still be wrong -- and M1.4 (#737), which gave these routes a second
credential, proves here that it did not open them up: the publication cookie
opens every one of them for the book it names and none of them for any other,
asserted at each door rather than at the one the ticket happened to mention.

The session endpoint itself is not one of these rows. It serves no part of a
publication and takes no second credential -- it is the Bearer-only route that
mints one -- so its own rules are in ``test_readium_session.py``.
"""

from collections.abc import Callable
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.infrastructure.identity.services.token_service import create_access_token
from src.infrastructure.web_reader.services.publication_token_service import (
    PUBLICATION_COOKIE_NAME,
)
from src.models import Book, User
from tests.conftest import create_test_book
from tests.test_readium_manifest import fixture_bytes, store_epub
from tests.test_readium_session import present, start_publication_session

# Every route that serves part of a publication, as a function from a book id to
# its URL. The resource path is one `minimal.epub` really contains, so a 404
# below is always the access rule talking and never a missing file.
READIUM_ENDPOINTS: dict[str, Callable[[int], str]] = {
    "manifest": lambda book_id: f"/api/v1/readium/books/{book_id}/manifest.json",
    "positions": lambda book_id: f"/api/v1/readium/books/{book_id}/positions.json",
    "resource": (lambda book_id: f"/api/v1/readium/books/{book_id}/resources/OEBPS/chapter1.xhtml"),
}

# What a publication's own bytes look like, so a refusal can be checked for not
# carrying any. Every one of these endpoints answers with XHTML or with JSON
# quoting it, and none of them has any business doing so in an error.
PUBLICATION_CONTENT = b"<html"


@pytest.fixture(params=list(READIUM_ENDPOINTS), ids=list(READIUM_ENDPOINTS))
def readium_url(request: pytest.FixtureRequest) -> Callable[[int], str]:
    """One web reader endpoint's URL builder, once per endpoint."""
    return READIUM_ENDPOINTS[request.param]


class TestReadiumAccess:
    """The access rules every publication endpoint shares."""

    async def test_requires_authentication(
        self,
        anonymous_client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
        readium_url: Callable[[int], str],
    ) -> None:
        """Should reject an unauthenticated request rather than serve the book.

        The book is real and readable, so only the missing credential can be
        what turns the request away.
        """
        await store_epub(db_session, test_book, storage_dir, fixture_bytes("minimal.epub"))

        response = await anonymous_client.get(readium_url(test_book.id))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text
        assert PUBLICATION_CONTENT not in response.content

    async def test_another_users_book_is_not_found(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        other_user: User,
        storage_dir: Path,
        readium_url: Callable[[int], str],
    ) -> None:
        """Should answer 404 for a perfectly readable book belonging to somebody else.

        Not 403: whether the book exists is itself somebody else's business.
        """
        their_book = await create_test_book(
            db_session=db_session, user_id=other_user.id, title="Not Yours"
        )
        await store_epub(db_session, their_book, storage_dir, fixture_bytes("minimal.epub"))

        response = await client.get(readium_url(their_book.id))

        assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
        assert PUBLICATION_CONTENT not in response.content

    async def test_unknown_book_is_not_found(
        self, client: AsyncClient, readium_url: Callable[[int], str]
    ) -> None:
        """Should answer 404 for a book id that exists for nobody."""
        response = await client.get(readium_url(99999))

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_book_without_an_epub_is_not_found(
        self, client: AsyncClient, test_book: Book, readium_url: Callable[[int], str]
    ) -> None:
        """Should answer 404 when the book was never given a file to read."""
        assert test_book.ebook_file is None

        response = await client.get(readium_url(test_book.id))

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_missing_epub_file_is_not_found(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        readium_url: Callable[[int], str],
    ) -> None:
        """Should answer 404 when the row names a file the store does not hold."""
        test_book.ebook_file = "vanished.epub"
        test_book.file_type = "epub"
        await db_session.commit()

        response = await client.get(readium_url(test_book.id))

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_unreadable_epub_is_rejected(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
        storage_dir: Path,
        readium_url: Callable[[int], str],
    ) -> None:
        """Should fail the request rather than answer 404 for a book it cannot parse.

        The book is the caller's and it is there; what is wrong is the file. A
        404 would send a reader looking for a book that exists.
        """
        await store_epub(db_session, test_book, storage_dir, b"not an epub at all")

        response = await client.get(readium_url(test_book.id))

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestTheSecondCredential:
    """The publication cookie (M1.4), asserted at every door the Bearer token opens."""

    async def test_the_cookie_opens_the_book_it_names(
        self,
        browser_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_book: Book,
        storage_dir: Path,
        readium_url: Callable[[int], str],
    ) -> None:
        """Should serve every publication endpoint to a request carrying only the cookie.

        No Authorization header anywhere in this test after the cookie is
        minted, which is the whole point: an iframe cannot send one.
        """
        await store_epub(db_session, test_book, storage_dir, fixture_bytes("minimal.epub"))
        minted = await start_publication_session(browser_client, test_user, test_book.id)
        assert minted.status_code == status.HTTP_200_OK, minted.text

        response = await browser_client.get(readium_url(test_book.id))

        assert response.status_code == status.HTTP_200_OK, response.text

    async def test_the_cookie_opens_no_other_book(
        self,
        browser_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_book: Book,
        storage_dir: Path,
        readium_url: Callable[[int], str],
    ) -> None:
        """Should refuse book A's cookie at every one of book B's doors.

        Both books are this user's and both are readable, so nothing but the
        book the token names can be what turns the request away. Presented at
        the root path on purpose: what is under test is the server's check, and
        a jar honouring the cookie's own path would answer by never sending it.
        """
        await store_epub(db_session, test_book, storage_dir, fixture_bytes("minimal.epub"))
        other_book = await create_test_book(
            db_session=db_session, user_id=test_user.id, title="Also Mine", client_book_id="other"
        )
        await store_epub(
            db_session, other_book, storage_dir, fixture_bytes("minimal.epub"), "other.epub"
        )
        minted = await start_publication_session(browser_client, test_user, test_book.id)
        present(browser_client, minted.cookies[PUBLICATION_COOKIE_NAME])

        response = await browser_client.get(readium_url(other_book.id))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text
        assert PUBLICATION_CONTENT not in response.content

    async def test_a_bearer_token_still_opens_everything(
        self,
        browser_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_book: Book,
        storage_dir: Path,
        readium_url: Callable[[int], str],
    ) -> None:
        """Should keep serving a plain Bearer request, cookie or no cookie.

        The rest of this file runs against a client whose authentication is
        overridden away; this one presents a real access token, so a second
        credential quietly displacing the first would show up here.
        """
        await store_epub(db_session, test_book, storage_dir, fixture_bytes("minimal.epub"))

        response = await browser_client.get(
            readium_url(test_book.id),
            headers={"Authorization": f"Bearer {create_access_token(test_user.id)}"},
        )

        assert response.status_code == status.HTTP_200_OK, response.text
