"""End-to-end checks on refresh-token rotation and its grace window.

Driven through the endpoint with the real repository, because the behaviour
under test is the interaction between what rotation records in the database and
what the next request makes of it.
"""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.domain.common.value_objects.ids import UserId
from src.domain.identity.entities.refresh_token import RefreshToken
from src.infrastructure.identity.orm.refresh_token_model import RefreshToken as RefreshTokenORM
from src.infrastructure.identity.repositories.refresh_token_repository import (
    RefreshTokenRepository,
)
from src.infrastructure.identity.services.password_service import hash_password
from src.infrastructure.identity.services.token_service import verify_refresh_token
from src.main import app
from src.models import User

PASSWORD = "correct-horse-battery-staple"

# The base_url host is a single label, and httpx's cookie jar stores such hosts
# with ".local" appended. A cookie planted under plain "test" is silently never
# sent, which would make every replay assertion below pass for want of a cookie
# rather than because the token was rejected.
COOKIE_DOMAIN = "test.local"


@pytest.fixture
async def auth_client(
    db_session: AsyncSession, test_user: User
) -> AsyncGenerator[AsyncClient, None]:
    """A client that carries the refresh cookie the way a browser does.

    ``https`` because the cookie is set ``Secure``: over ``http`` the cookie jar
    would drop it silently and every test here would pass for the wrong reason.
    """
    test_user.hashed_password = await hash_password(PASSWORD)
    await db_session.commit()
    await db_session.refresh(test_user)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as client:
        yield client
    app.dependency_overrides.clear()


async def _login(client: AsyncClient, user: User) -> None:
    response = await client.post(
        "/api/v1/auth/login", data={"username": user.email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text


def _cookie(client: AsyncClient) -> str:
    token = client.cookies.get("refresh_token")
    assert token is not None
    return token


def _present(client: AsyncClient, token: str) -> None:
    """Replace whatever the client currently holds with ``token``.

    The jar has to be cleared first: ``set`` adds an entry rather than
    overwriting the host-only one the server sent, and two ``refresh_token``
    cookies on one request would let the server read the wrong token.
    """
    client.cookies.clear()
    client.cookies.set("refresh_token", token, domain=COOKIE_DOMAIN, path="/api/v1/auth")


def _jti_of(refresh_token: str) -> str:
    claims = verify_refresh_token(refresh_token)
    assert claims is not None
    return claims.jti


async def _age_revocation(session: AsyncSession, jti: str, age: timedelta) -> None:
    """Backdate a rotation so the grace window has demonstrably passed."""
    await session.execute(
        update(RefreshTokenORM)
        .where(RefreshTokenORM.jti == jti)
        .values(revoked_at=datetime.now(UTC) - age)
    )
    await session.commit()


async def test_refresh_rotates_the_cookie_and_returns_a_working_token(
    auth_client: AsyncClient, test_user: User
) -> None:
    await _login(auth_client, test_user)
    first = _cookie(auth_client)

    response = await auth_client.post("/api/v1/auth/refresh")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert body["refresh_token"] != first
    assert _cookie(auth_client) == body["refresh_token"]

    me = await auth_client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.status_code == 200, me.text
    assert me.json()["email"] == test_user.email


async def test_a_client_that_lost_the_rotation_response_gets_the_same_successor(
    auth_client: AsyncClient, test_user: User
) -> None:
    """The case that logs phones out: the reply never arrived, so the client retries.

    This is also the shape of two refreshes racing — both present the cookie
    that was current when they were sent.
    """
    await _login(auth_client, test_user)
    spent = _cookie(auth_client)

    first = await auth_client.post("/api/v1/auth/refresh")
    assert first.status_code == 200, first.text

    _present(auth_client, spent)
    retried = await auth_client.post("/api/v1/auth/refresh")

    assert retried.status_code == 200, retried.text
    # The same successor, not a second one: a fork would leave two live tokens
    # in one family and only postpone the logout.
    assert retried.json()["refresh_token"] == first.json()["refresh_token"]
    assert _cookie(auth_client) == first.json()["refresh_token"]

    me = await auth_client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {retried.json()['access_token']}"},
    )
    assert me.status_code == 200, me.text

    # And the session keeps rotating normally afterwards.
    assert (await auth_client.post("/api/v1/auth/refresh")).status_code == 200


async def test_reuse_after_the_grace_window_revokes_the_whole_family(
    auth_client: AsyncClient, db_session: AsyncSession, test_user: User
) -> None:
    """Replay detection still fires — this is what the grace window trades against."""
    await _login(auth_client, test_user)
    stolen = _cookie(auth_client)

    rotated = await auth_client.post("/api/v1/auth/refresh")
    assert rotated.status_code == 200, rotated.text
    successor = rotated.json()["refresh_token"]

    await _age_revocation(db_session, _jti_of(stolen), timedelta(hours=1))

    _present(auth_client, stolen)
    replayed = await auth_client.post("/api/v1/auth/refresh")
    assert replayed.status_code == 401, replayed.text

    # The token the legitimate client holds is dead too: that is what family
    # revocation is for.
    _present(auth_client, successor)
    assert (await auth_client.post("/api/v1/auth/refresh")).status_code == 401


async def test_a_second_generation_behind_is_replay_even_inside_the_window(
    auth_client: AsyncClient, test_user: User
) -> None:
    """A recent rotation is not enough; the successor must still be unspent."""
    await _login(auth_client, test_user)
    oldest = _cookie(auth_client)

    assert (await auth_client.post("/api/v1/auth/refresh")).status_code == 200
    assert (await auth_client.post("/api/v1/auth/refresh")).status_code == 200

    _present(auth_client, oldest)
    assert (await auth_client.post("/api/v1/auth/refresh")).status_code == 401


async def test_logout_is_final_even_inside_the_grace_window(
    auth_client: AsyncClient, test_user: User
) -> None:
    """A token revoked rather than rotated records no successor to hand back."""
    await _login(auth_client, test_user)
    token = _cookie(auth_client)

    assert (await auth_client.post("/api/v1/auth/logout")).status_code == 200

    _present(auth_client, token)
    assert (await auth_client.post("/api/v1/auth/refresh")).status_code == 401


async def test_refresh_without_a_cookie_is_rejected(auth_client: AsyncClient) -> None:
    response = await auth_client.post("/api/v1/auth/refresh")
    assert response.status_code == 401, response.text


async def test_a_forged_refresh_token_is_rejected(auth_client: AsyncClient) -> None:
    _present(auth_client, "not.a.jwt")
    response = await auth_client.post("/api/v1/auth/refresh")
    assert response.status_code == 401, response.text


async def test_rotation_records_the_successor_it_handed_out(
    auth_client: AsyncClient, db_session: AsyncSession, test_user: User
) -> None:
    """The link the grace window reads has to actually be written."""
    await _login(auth_client, test_user)
    repository = RefreshTokenRepository(db_session)

    before = await repository.find_by_jti(_jti_of(_cookie(auth_client)))
    assert before is not None
    assert before.replaced_by_jti is None

    response = await auth_client.post("/api/v1/auth/refresh")
    assert response.status_code == 200, response.text

    spent = await repository.find_by_jti(before.jti)
    assert spent is not None
    assert spent.is_revoked
    assert spent.replaced_by_jti == _jti_of(response.json()["refresh_token"])

    assert spent.replaced_by_jti is not None
    successor = await repository.find_by_jti(spent.replaced_by_jti)
    assert successor is not None
    assert not successor.is_revoked
    assert successor.family_id == spent.family_id


async def test_refresh_clears_a_users_expired_tokens(
    auth_client: AsyncClient, db_session: AsyncSession, test_user: User
) -> None:
    await _login(auth_client, test_user)
    repository = RefreshTokenRepository(db_session)
    await repository.save(
        RefreshToken.create(
            jti="jti-long-expired",
            user_id=UserId(test_user.id),
            family_id="family-long-expired",
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
    )

    assert (await auth_client.post("/api/v1/auth/refresh")).status_code == 200

    assert await repository.find_by_jti("jti-long-expired") is None
