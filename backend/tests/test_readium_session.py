"""The publication cookie: what mints it, what it opens, and how it fails (M1.4, #737).

A navigator loads every resource of a publication into an iframe, and an iframe
sends cookies and nothing else. So the reader asks for a cookie with the Bearer
token it does have, and the cookie carries the rest of the reading session.

These tests drive the real credential end to end -- a real access token in, a
real signed cookie back, and the reading endpoints entered with no Authorization
header at all, the way the iframe enters them. What each endpoint then *serves*
is M1.1-M1.3's business; what is asserted here is who gets in.
"""

from pathlib import Path

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.infrastructure.identity.services.token_service import create_access_token
from src.infrastructure.web_reader.services import publication_token_service
from src.infrastructure.web_reader.services.publication_token_service import (
    PUBLICATION_COOKIE_NAME,
    create_publication_token,
)
from src.models import Book, User
from tests.conftest import create_test_book
from tests.test_readium_manifest import fixture_bytes, store_epub

# The base_url host is a single label, and httpx's cookie jar stores such hosts
# with ".local" appended. A cookie planted under plain "test" is silently never
# sent, which would leave a test asserting a refusal that no credential was
# offered for.
COOKIE_DOMAIN = "test.local"

# What the reader is expected to have been able to load: `minimal.epub` really
# contains this file, so a refusal here is always the credential talking.
RESOURCE_PATH = "resources/OEBPS/chapter1.xhtml"


def session_url(book_id: int) -> str:
    return f"/api/v1/readium/books/{book_id}/session"


def resource_url(book_id: int) -> str:
    return f"/api/v1/readium/books/{book_id}/{RESOURCE_PATH}"


async def start_publication_session(
    browser_client: AsyncClient, user: User, book_id: int
) -> Response:
    """Ask for a publication cookie the way the SPA does: with a real access token."""
    return await browser_client.post(
        session_url(book_id),
        headers={"Authorization": f"Bearer {create_access_token(user.id)}"},
    )


def present(browser_client: AsyncClient, token: str, path: str = "/") -> None:
    """Put ``token`` in the jar under ``path``, replacing whatever is there.

    The default path is the whole API rather than one book's: what is under test
    is what the *server* makes of a token presented where it does not belong,
    and a jar honouring the cookie's own path would answer that question by
    never sending it.
    """
    browser_client.cookies.clear()
    browser_client.cookies.set(PUBLICATION_COOKIE_NAME, token, domain=COOKIE_DOMAIN, path=path)


@pytest.fixture
async def readable_book(db_session: AsyncSession, test_book: Book, storage_dir: Path) -> Book:
    """The user's own book, with an EPUB behind it that really parses."""
    await store_epub(db_session, test_book, storage_dir, fixture_bytes("minimal.epub"))
    return test_book


@pytest.fixture
async def second_book(db_session: AsyncSession, test_user: User, storage_dir: Path) -> Book:
    """A second book of the same user's, to prove one book's cookie is one book's."""
    book = await create_test_book(
        db_session=db_session, user_id=test_user.id, title="Also Mine", client_book_id="book-2"
    )
    await store_epub(db_session, book, storage_dir, fixture_bytes("minimal.epub"), "second.epub")
    return book


class TestStartingASession:
    """Minting the cookie: who may, and what comes back."""

    async def test_sets_a_cookie_scoped_to_this_books_paths(
        self, browser_client: AsyncClient, test_user: User, readable_book: Book
    ) -> None:
        """Should hand back an httpOnly, Secure, same-site cookie for this book alone."""
        response = await start_publication_session(browser_client, test_user, readable_book.id)

        assert response.status_code == status.HTTP_200_OK, response.text
        set_cookie = response.headers["set-cookie"]
        assert set_cookie.startswith(f"{PUBLICATION_COOKIE_NAME}=")
        assert "HttpOnly" in set_cookie
        assert "Secure" in set_cookie
        assert "SameSite=strict" in set_cookie
        assert f"Path=/api/v1/readium/books/{readable_book.id}/" in set_cookie
        # The browser drops it exactly when the token inside it dies.
        assert f"Max-Age={response.json()['expires_in']}" in set_cookie

    async def test_says_when_the_cookie_expires(
        self, browser_client: AsyncClient, test_user: User, readable_book: Book
    ) -> None:
        """Should tell the page how long it has, since httpOnly means it cannot look.

        Bounded above by the access token's own lifetime: a credential that
        outlived the token that bought it would keep a session reading after the
        session was over.
        """
        response = await start_publication_session(browser_client, test_user, readable_book.id)

        expires_in = response.json()["expires_in"]
        assert 0 < expires_in <= publication_token_service.PUBLICATION_TOKEN_EXPIRE_MINUTES * 60

    async def test_an_unauthenticated_request_gets_no_cookie(
        self, browser_client: AsyncClient, readable_book: Book
    ) -> None:
        """Should refuse to mint without a Bearer token -- the cookie has no other source."""
        response = await browser_client.post(session_url(readable_book.id))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text
        assert "set-cookie" not in response.headers

    async def test_another_users_book_gets_no_cookie(
        self,
        browser_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        other_user: User,
    ) -> None:
        """Should answer 404 for somebody else's book, as every book route does."""
        theirs = await create_test_book(
            db_session=db_session, user_id=other_user.id, title="Not Yours"
        )

        response = await start_publication_session(browser_client, test_user, theirs.id)

        assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
        assert "set-cookie" not in response.headers

    async def test_an_unknown_book_gets_no_cookie(
        self, browser_client: AsyncClient, test_user: User
    ) -> None:
        response = await start_publication_session(browser_client, test_user, 99999)

        assert response.status_code == status.HTTP_404_NOT_FOUND, response.text


class TestReadingWithTheCookie:
    """What the cookie is for: a request that carries no Authorization header."""

    async def test_the_cookie_alone_serves_the_books_resources(
        self, browser_client: AsyncClient, test_user: User, readable_book: Book
    ) -> None:
        """Should serve the file to an iframe-shaped request: cookie, no header."""
        assert (
            await start_publication_session(browser_client, test_user, readable_book.id)
        ).status_code == status.HTTP_200_OK

        response = await browser_client.get(resource_url(readable_book.id))

        assert response.status_code == status.HTTP_200_OK, response.text
        assert b"<html" in response.content
        assert "Authorization" not in browser_client.headers

    async def test_no_credential_at_all_is_still_refused(
        self, browser_client: AsyncClient, readable_book: Book
    ) -> None:
        """The same request without the cookie, to show the cookie is what let it in."""
        response = await browser_client.get(resource_url(readable_book.id))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text
        assert b"<html" not in response.content


class TestACookieOpensOneBook:
    """The claim the server checks that the browser's path scoping only suggests."""

    async def test_a_cookie_for_another_book_is_refused(
        self,
        browser_client: AsyncClient,
        test_user: User,
        readable_book: Book,
        second_book: Book,
    ) -> None:
        """Should refuse book A's cookie on book B, though both books are the caller's.

        401 rather than 404: the caller has presented no valid credential *for
        this book*, and answering 404 would mean telling a token scoped to one
        book whether another one exists.
        """
        minted = await start_publication_session(browser_client, test_user, readable_book.id)
        token = minted.cookies[PUBLICATION_COOKIE_NAME]
        present(browser_client, token)

        refused = await browser_client.get(resource_url(second_book.id))
        assert refused.status_code == status.HTTP_401_UNAUTHORIZED, refused.text
        assert b"<html" not in refused.content

        # The very same cookie, sent to the book it was issued for, works: what
        # was rejected was the mismatch and not the token.
        allowed = await browser_client.get(resource_url(readable_book.id))
        assert allowed.status_code == status.HTTP_200_OK, allowed.text


class TestACookieThatIsNoGood:
    """Every way a presented cookie can fail to be a credential."""

    async def test_an_expired_cookie_is_refused(
        self,
        browser_client: AsyncClient,
        readable_book: Book,
        test_user: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Should refuse a token whose ``exp`` has passed, signature and all.

        Minted through the real signing with the clock against it, because a
        browser that kept a cookie past ``Max-Age`` is exactly the case the
        server may not trust the browser for.
        """
        monkeypatch.setattr(publication_token_service, "PUBLICATION_TOKEN_EXPIRE_MINUTES", -1)
        present(browser_client, create_publication_token(test_user.id, readable_book.id))

        response = await browser_client.get(resource_url(readable_book.id))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text
        assert b"<html" not in response.content

    async def test_a_tampered_cookie_is_refused(
        self, browser_client: AsyncClient, test_user: User, readable_book: Book
    ) -> None:
        """Should refuse a token re-signed by nobody: one flipped character is enough."""
        minted = await start_publication_session(browser_client, test_user, readable_book.id)
        token = minted.cookies[PUBLICATION_COOKIE_NAME]
        payload, signature = token.rsplit(".", 1)
        forged = f"{payload}.{'x' * len(signature)}"
        present(browser_client, forged)

        response = await browser_client.get(resource_url(readable_book.id))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text
        assert b"<html" not in response.content

    async def test_nonsense_in_the_cookie_is_refused(
        self, browser_client: AsyncClient, readable_book: Book
    ) -> None:
        present(browser_client, "not.a.jwt")

        response = await browser_client.get(resource_url(readable_book.id))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text

    async def test_a_publication_token_is_not_an_access_token(
        self, browser_client: AsyncClient, test_user: User, readable_book: Book
    ) -> None:
        """The cookie must not be spendable as a Bearer token.

        It is signed with the same key as an access token, so what keeps the
        narrower credential from buying the wider one is the ``type`` claim --
        and this is where that is worth proving, since the token is handed to a
        page that could try it anywhere.
        """
        minted = await start_publication_session(browser_client, test_user, readable_book.id)
        token = minted.cookies[PUBLICATION_COOKIE_NAME]

        response = await browser_client.get(
            "/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text

    async def test_a_broken_bearer_token_is_not_rescued_by_a_good_cookie(
        self, browser_client: AsyncClient, test_user: User, readable_book: Book
    ) -> None:
        """A presented Authorization header has to verify, cookie or no cookie.

        Falling back would mean a client with a stale token never learning that
        it is stale.
        """
        assert (
            await start_publication_session(browser_client, test_user, readable_book.id)
        ).status_code == status.HTTP_200_OK

        response = await browser_client.get(
            resource_url(readable_book.id), headers={"Authorization": "Bearer nonsense"}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text


class TestTheCookieIsNotAKeyToTheRestOfTheAPI:
    """What the path scoping buys, asserted through a jar that honours it."""

    async def test_the_browser_sends_it_only_to_this_books_routes(
        self,
        browser_client: AsyncClient,
        test_user: User,
        readable_book: Book,
        second_book: Book,
    ) -> None:
        """Should leave the rest of the API unauthenticated, cookie in hand.

        The cookie stays where the server put it: a jar that honours ``Path``
        sends it to this book's endpoints, and offers it to no other book and to
        nothing else in the API.
        """
        assert (
            await start_publication_session(browser_client, test_user, readable_book.id)
        ).status_code == status.HTTP_200_OK

        assert (await browser_client.get(resource_url(readable_book.id))).status_code == (
            status.HTTP_200_OK
        )
        assert (await browser_client.get(resource_url(second_book.id))).status_code == (
            status.HTTP_401_UNAUTHORIZED
        )
        assert (await browser_client.get("/api/v1/users/me")).status_code == (
            status.HTTP_401_UNAUTHORIZED
        )
