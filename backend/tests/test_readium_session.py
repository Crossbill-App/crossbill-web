"""Minting the publication cookie, and what the verifier makes of one.

The endpoint is driven with a real access token through ``browser_client``, so
the cookie that comes back is the one a browser would be given. The verifier is
called directly: the routes that consult it belong to a later ticket.
"""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.infrastructure.identity.services import token_service
from src.infrastructure.identity.services.token_service import create_access_token
from src.infrastructure.web_reader.services import publication_token_service
from src.infrastructure.web_reader.services.publication_token_service import (
    ALGORITHM,
    PUBLICATION_COOKIE_NAME,
    PUBLICATION_TOKEN_EXPIRE_MINUTES,
    PUBLICATION_TOKEN_SECRET_KEY,
    PUBLICATION_TOKEN_TYPE,
    PublicationTokenClaims,
    create_publication_token,
    verify_publication_token,
)
from src.models import Book, User
from tests.readium_helpers import another_users_book


def session_url(book_id: int) -> str:
    return f"/api/v1/readium/books/{book_id}/session"


async def start_session(browser_client: AsyncClient, user_id: int, book_id: int) -> Response:
    return await browser_client.post(
        session_url(book_id),
        headers={"Authorization": f"Bearer {create_access_token(user_id)}"},
    )


def _sign(claims: dict[str, object]) -> str:
    return jwt.encode(claims, PUBLICATION_TOKEN_SECRET_KEY, algorithm=ALGORITHM)


def _future() -> datetime:
    return datetime.now(UTC) + timedelta(minutes=5)


class TestStartingAPublicationSession:
    async def test_the_cookie_is_httponly_secure_and_scoped_to_this_book(
        self, browser_client: AsyncClient, test_user: User, test_book: Book
    ) -> None:
        response = await start_session(browser_client, test_user.id, test_book.id)

        assert response.status_code == status.HTTP_200_OK, response.text
        set_cookie = response.headers["set-cookie"]
        assert set_cookie.startswith(f"{PUBLICATION_COOKIE_NAME}=")
        assert "HttpOnly" in set_cookie
        assert "Secure" in set_cookie
        assert "SameSite=strict" in set_cookie
        # The path is what keeps one book's cookie out of another book's routes.
        assert f"Path=/api/v1/readium/books/{test_book.id}/" in set_cookie

    async def test_the_cookie_names_the_caller_and_the_book_asked_for(
        self, browser_client: AsyncClient, test_user: User, test_book: Book
    ) -> None:
        response = await start_session(browser_client, test_user.id, test_book.id)

        claims = verify_publication_token(response.cookies[PUBLICATION_COOKIE_NAME])

        # The path scopes what a browser sends; the claim is what #801 authorises
        # on, so a cookie naming another book would read it through this path.
        assert claims == PublicationTokenClaims(user_id=test_user.id, book_id=test_book.id)

    async def test_the_body_says_when_the_browser_will_drop_the_cookie(
        self, browser_client: AsyncClient, test_user: User, test_book: Book
    ) -> None:
        response = await start_session(browser_client, test_user.id, test_book.id)

        expires_in = response.json()["expires_in"]
        assert 0 < expires_in <= PUBLICATION_TOKEN_EXPIRE_MINUTES * 60
        assert f"Max-Age={expires_in}" in response.headers["set-cookie"]

    async def test_a_nearly_spent_access_token_caps_the_cookie(
        self,
        browser_client: AsyncClient,
        test_user: User,
        test_book: Book,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(token_service, "ACCESS_TOKEN_EXPIRE_MINUTES", 1)

        response = await start_session(browser_client, test_user.id, test_book.id)

        expires_in = response.json()["expires_in"]
        assert 0 < expires_in <= 60, (
            f"the cookie outlived the access token that minted it: {expires_in}s"
        )
        assert f"Max-Age={expires_in}" in response.headers["set-cookie"]

    async def test_a_spent_access_token_is_refused_rather_than_answered(
        self, browser_client: AsyncClient, test_user: User, test_book: Book
    ) -> None:
        # Valid, so it reaches the route, but with under a second left: the
        # `Max-Age=0` it would otherwise buy deletes the cookie already held.
        nearly_spent = jwt.encode(
            {
                "sub": str(test_user.id),
                "type": "access",
                "exp": datetime.now(UTC) + timedelta(milliseconds=500),
            },
            token_service.SECRET_KEY,
            algorithm=token_service.ALGORITHM,
        )

        response = await browser_client.post(
            session_url(test_book.id), headers={"Authorization": f"Bearer {nearly_spent}"}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text

    async def test_without_a_bearer_token_nothing_is_minted(
        self, browser_client: AsyncClient, test_book: Book
    ) -> None:
        response = await browser_client.post(session_url(test_book.id))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text

    async def test_another_users_book_mints_nothing(
        self, browser_client: AsyncClient, db_session: AsyncSession, test_user: User
    ) -> None:
        theirs = await another_users_book(db_session)

        response = await start_session(browser_client, test_user.id, theirs.id)

        assert response.status_code == status.HTTP_404_NOT_FOUND, response.text

    async def test_an_unknown_book_mints_nothing(
        self, browser_client: AsyncClient, test_user: User
    ) -> None:
        response = await start_session(browser_client, test_user.id, 999999)

        assert response.status_code == status.HTTP_404_NOT_FOUND, response.text

    async def test_the_minted_token_is_refused_as_a_bearer_token(
        self, browser_client: AsyncClient, test_user: User, test_book: Book
    ) -> None:
        minted = await start_session(browser_client, test_user.id, test_book.id)
        token = minted.cookies[PUBLICATION_COOKIE_NAME]

        response = await browser_client.get(
            "/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text


class TestVerifyingAPublicationToken:
    def test_a_minted_token_names_its_user_and_its_book(self) -> None:
        token = create_publication_token(7, 42, not_after=_future())

        claims = verify_publication_token(token.value)

        assert claims is not None
        assert claims.user_id == 7
        assert claims.book_id == 42

    def test_the_ttl_caps_a_token_bought_with_a_long_lived_access_token(self) -> None:
        # An access token issued before the TTL was lowered still carries the
        # longer `exp`; the cap is what stops it buying the longer read.
        far_future = datetime.now(UTC) + timedelta(days=1)

        token = create_publication_token(7, 42, not_after=far_future)

        ceiling = PUBLICATION_TOKEN_EXPIRE_MINUTES * 60
        assert 0 < token.expires_in <= ceiling, (
            f"the TTL did not cap a far-future not_after: {token.expires_in}s > {ceiling}s"
        )

    def test_signing_and_verifying_agree_on_a_non_default_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Whether the *setting* is read is not observable here: the module binds
        # the key at import, so only the bound constant can be moved.
        monkeypatch.setattr(
            publication_token_service,
            "PUBLICATION_TOKEN_SECRET_KEY",
            "a-publication-key-of-at-least-32-bytes",
        )
        token = create_publication_token(7, 42, not_after=_future())

        assert verify_publication_token(token.value) == PublicationTokenClaims(
            user_id=7, book_id=42
        )
        assert verify_publication_token(create_access_token(7)) is None

    def test_an_expired_token_is_refused(self) -> None:
        already_over = datetime.now(UTC) - timedelta(seconds=1)
        token = create_publication_token(7, 42, not_after=already_over)

        assert verify_publication_token(token.value) is None

    def test_a_tampered_signature_is_refused(self) -> None:
        token = create_publication_token(7, 42, not_after=_future())
        payload, signature = token.value.rsplit(".", 1)

        assert verify_publication_token(f"{payload}.{'x' * len(signature)}") is None

    def test_a_token_signed_with_another_key_is_refused(self) -> None:
        claims = {"sub": "7", "book": "42", "exp": _future(), "type": PUBLICATION_TOKEN_TYPE}
        forged = jwt.encode(claims, "another-key-of-at-least-32-bytes-long", algorithm=ALGORITHM)

        assert verify_publication_token(forged) is None

    def test_an_access_token_is_refused(self) -> None:
        assert verify_publication_token(create_access_token(7)) is None

    def test_a_token_of_another_type_is_refused_though_it_names_a_book(self) -> None:
        token = _sign({"sub": "7", "book": "42", "exp": _future(), "type": "access"})

        assert verify_publication_token(token) is None

    def test_a_token_naming_no_user_is_refused(self) -> None:
        token = _sign({"book": "42", "exp": _future(), "type": PUBLICATION_TOKEN_TYPE})

        assert verify_publication_token(token) is None

    def test_a_token_naming_no_book_is_refused(self) -> None:
        token = _sign({"sub": "7", "exp": _future(), "type": PUBLICATION_TOKEN_TYPE})

        assert verify_publication_token(token) is None

    def test_a_token_whose_book_is_not_a_number_is_refused(self) -> None:
        token = _sign(
            {"sub": "7", "book": "forty-two", "exp": _future(), "type": PUBLICATION_TOKEN_TYPE}
        )

        assert verify_publication_token(token) is None
