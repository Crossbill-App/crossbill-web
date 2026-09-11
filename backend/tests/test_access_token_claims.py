"""What ``verify_access_token`` accepts, and what it reports about the token.

Driven through ``/api/v1/users/me`` wherever the refusal is observable there;
the expiry the claims carry is not, so that one calls the service directly.
"""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient, Response

from src.infrastructure.identity.services import token_service
from src.infrastructure.identity.services.token_service import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    create_refresh_token,
    verify_access_token,
)
from src.models import User


def _sign(claims: dict[str, object]) -> str:
    return jwt.encode(claims, SECRET_KEY, algorithm=ALGORITHM)


async def _me(client: AsyncClient, token: str) -> Response:
    return await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})


def _future() -> datetime:
    return datetime.now(UTC) + timedelta(minutes=5)


async def test_a_refresh_token_is_not_accepted_as_an_access_token(
    browser_client: AsyncClient, monkeypatch: pytest.MonkeyPatch, test_user: User
) -> None:
    # Signed with the access key, as it is wherever REFRESH_TOKEN_SECRET_KEY is
    # unset: there the ``type`` claim is the only thing telling the two apart.
    monkeypatch.setattr(token_service, "REFRESH_TOKEN_SECRET_KEY", SECRET_KEY)
    token = create_refresh_token(test_user.id, "some-jti", _future())

    response = await _me(browser_client, token)

    assert response.status_code == 401, response.text


async def test_a_token_without_a_type_claim_is_refused(
    browser_client: AsyncClient, test_user: User
) -> None:
    token = _sign({"sub": str(test_user.id), "exp": _future()})

    response = await _me(browser_client, token)

    assert response.status_code == 401, response.text


async def test_a_token_of_another_type_is_refused(
    browser_client: AsyncClient, test_user: User
) -> None:
    token = _sign({"sub": str(test_user.id), "exp": _future(), "type": "publication"})

    response = await _me(browser_client, token)

    assert response.status_code == 401, response.text


async def test_a_token_without_an_expiry_is_refused(
    browser_client: AsyncClient, test_user: User
) -> None:
    token = _sign({"sub": str(test_user.id), "type": "access"})

    response = await _me(browser_client, token)

    assert response.status_code == 401, response.text


async def test_the_claims_report_the_expiry_the_token_was_minted_with(
    monkeypatch: pytest.MonkeyPatch, test_user: User
) -> None:
    monkeypatch.setattr(token_service, "ACCESS_TOKEN_EXPIRE_MINUTES", 1)
    before = datetime.now(UTC)

    claims = verify_access_token(create_access_token(test_user.id))

    assert claims is not None
    assert claims.user_id == test_user.id
    assert claims.expires_at.utcoffset() == timedelta(0)
    assert abs(claims.expires_at - (before + timedelta(minutes=1))) < timedelta(seconds=2)


async def test_a_token_whose_expiry_is_not_a_number_is_refused(
    browser_client: AsyncClient, test_user: User
) -> None:
    token = _sign(
        {"sub": str(test_user.id), "type": "access", "exp": str(int(_future().timestamp()))}
    )

    response = await _me(browser_client, token)

    assert response.status_code == 401, response.text
