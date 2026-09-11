"""Who gets into the three routes a navigator's iframe loads (#801).

An iframe load carries no ``Authorization`` header, so the manifest, the position
list and the resources take the publication cookie and nothing else -- not even a
valid Bearer token. Every request here is driven through ``browser_client``,
which authenticates nothing on its own, so what is asserted is the credential.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient, Cookies, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src import models
from src.infrastructure.identity.services.token_service import create_access_token
from src.infrastructure.web_reader.services.publication_token_service import (
    PUBLICATION_COOKIE_NAME,
    create_publication_token,
)
from tests.conftest import create_test_book
from tests.readium_helpers import fixture_bytes, manifest_url, positions_url, store_fixture
from tests.test_readium_resources import CHAPTER_1, resource_url, store_indexed_epub
from tests.test_readium_session import start_session

# httpx's jar stores a single-label host with ".local" appended, so a cookie
# planted under plain "test" is silently never sent -- and a test asserting a
# refusal would be asserting that nothing was offered.
COOKIE_DOMAIN = "test.local"

ROUTE_URLS: list[Callable[[int], str]] = [
    manifest_url,
    positions_url,
    lambda book_id: resource_url(book_id, CHAPTER_1),
]
ROUTE_NAMES = ["manifest", "positions", "resource"]


def present(browser_client: AsyncClient, token: str) -> None:
    """Put ``token`` in the jar under the whole API, replacing whatever is there.

    The path is deliberately wider than the server's: what is under test is what
    the server makes of a cookie presented where it does not belong, and a jar
    honouring the cookie's own path would answer by never sending it.
    """
    browser_client.cookies.clear()
    browser_client.cookies.set(PUBLICATION_COOKIE_NAME, token, domain=COOKIE_DOMAIN, path="/")


def would_send(jar: Cookies, url: str) -> bool:
    """Whether a jar honouring ``Path`` offers the publication cookie to ``url``."""
    request = Request("GET", url)
    jar.set_cookie_header(request)
    return PUBLICATION_COOKIE_NAME in request.headers.get("cookie", "")


@pytest.fixture
async def readable_book(
    db_session: AsyncSession, test_book: models.Book, storage_dir: Path
) -> models.Book:
    """The user's own book, indexed and on disk, so all three routes have an answer."""
    await store_indexed_epub(db_session, test_book, storage_dir, fixture_bytes("nested_toc"))
    return test_book


@pytest.fixture
async def second_book(
    db_session: AsyncSession, test_user: models.User, storage_dir: Path
) -> models.Book:
    """A second book of the same user's, so a mismatch is never about ownership."""
    book = await create_test_book(db_session=db_session, user_id=test_user.id, title="Also Mine")
    await store_fixture(db_session, book, "minimal")
    return book


class TestTheCookieAloneIsEnough:
    async def test_the_cookie_alone_serves_the_manifest(
        self, browser_client: AsyncClient, test_user: models.User, readable_book: models.Book
    ) -> None:
        await start_session(browser_client, test_user.id, readable_book.id)

        response = await browser_client.get(manifest_url(readable_book.id))

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["readingOrder"], response.text

    async def test_the_cookie_alone_serves_the_position_list(
        self, browser_client: AsyncClient, test_user: models.User, readable_book: models.Book
    ) -> None:
        await start_session(browser_client, test_user.id, readable_book.id)

        response = await browser_client.get(positions_url(readable_book.id))

        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json()["total"] > 0, response.text

    async def test_the_cookie_alone_serves_a_resource(
        self, browser_client: AsyncClient, test_user: models.User, readable_book: models.Book
    ) -> None:
        await start_session(browser_client, test_user.id, readable_book.id)

        response = await browser_client.get(resource_url(readable_book.id, CHAPTER_1))

        assert response.status_code == status.HTTP_200_OK, response.text
        assert b"<html" in response.content


class TestEveryOtherCredentialIsRefused:
    @pytest.mark.parametrize("url_for", ROUTE_URLS, ids=ROUTE_NAMES)
    async def test_no_credential_at_all_is_refused(
        self,
        browser_client: AsyncClient,
        readable_book: models.Book,
        url_for: Callable[[int], str],
    ) -> None:
        response = await browser_client.get(url_for(readable_book.id))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text
        assert b"<html" not in response.content

    async def test_a_bearer_token_alone_is_refused(
        self, browser_client: AsyncClient, test_user: models.User, readable_book: models.Book
    ) -> None:
        # The owner's own, perfectly valid access token: these routes take the
        # cookie or nothing, so the SPA has to mint one before it can read.
        response = await browser_client.get(
            manifest_url(readable_book.id),
            headers={"Authorization": f"Bearer {create_access_token(test_user.id)}"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text


class TestACookieOpensOneBook:
    async def test_a_cookie_minted_for_another_book_is_refused_rather_than_hidden(
        self,
        browser_client: AsyncClient,
        test_user: models.User,
        readable_book: models.Book,
        second_book: models.Book,
    ) -> None:
        minted = await start_session(browser_client, test_user.id, second_book.id)
        present(browser_client, minted.cookies[PUBLICATION_COOKIE_NAME])

        refused = await browser_client.get(manifest_url(readable_book.id))

        # 401 and not 404: the caller is unauthenticated here, and 404 would tell
        # a credential scoped to one book whether another one exists.
        assert refused.status_code == status.HTTP_401_UNAUTHORIZED, refused.text
        # The same cookie on its own book works, so it was the mismatch refused.
        allowed = await browser_client.get(manifest_url(second_book.id))
        assert allowed.status_code == status.HTTP_200_OK, allowed.text

    async def test_the_browser_sends_the_cookie_only_to_this_books_routes(
        self, browser_client: AsyncClient, test_user: models.User, readable_book: models.Book
    ) -> None:
        minted = await start_session(browser_client, test_user.id, readable_book.id)
        jar = Cookies()
        jar.extract_cookies(minted)

        for url_for in ROUTE_URLS:
            url = f"https://test{url_for(readable_book.id)}"
            assert would_send(jar, url), f"the jar withheld the cookie from {url}"
        # A book whose id merely starts with this one's. What this guards is the
        # book in the cookie's path: scoped to `/readium/` it would reach both.
        collides = f"https://test{manifest_url(readable_book.id)}".replace(
            f"/books/{readable_book.id}/", f"/books/{readable_book.id}0/"
        )
        assert not would_send(jar, collides)
        assert not would_send(jar, "https://test/api/v1/users/me")

    async def test_the_cookie_is_not_a_key_to_the_rest_of_the_api(
        self, browser_client: AsyncClient, test_user: models.User, readable_book: models.Book
    ) -> None:
        minted = await start_session(browser_client, test_user.id, readable_book.id)
        present(browser_client, minted.cookies[PUBLICATION_COOKIE_NAME])

        response = await browser_client.get("/api/v1/users/me")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text


class TestACookieThatIsNoGood:
    """What the route makes of a cookie the verifier rejects.

    Which cookies it rejects -- expired, tampered, foreign key, wrong type,
    claim-less -- is ``test_readium_session.TestVerifyingAPublicationToken``.
    """

    async def test_a_cookie_the_verifier_rejects_is_refused(
        self, browser_client: AsyncClient, test_user: models.User, readable_book: models.Book
    ) -> None:
        already_over = datetime.now(UTC) - timedelta(seconds=1)
        expired = create_publication_token(test_user.id, readable_book.id, not_after=already_over)
        present(browser_client, expired.value)

        response = await browser_client.get(manifest_url(readable_book.id))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text
