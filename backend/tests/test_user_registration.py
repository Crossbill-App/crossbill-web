"""Tests for POST /users/register."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.models import User

EMAIL = "new-reader@example.com"
PASSWORD = "a-long-enough-password"


def allow_registrations(monkeypatch: pytest.MonkeyPatch, *, enabled: bool) -> None:
    monkeypatch.setattr(
        "src.application.identity.commands.register_user_use_case.is_user_registrations_enabled",
        lambda: enabled,
    )


async def register(client: AsyncClient) -> dict[str, object]:
    response = await client.post(
        "/api/v1/users/register", json={"email": EMAIL, "password": PASSWORD}
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()


async def email_of(client: AsyncClient, access_token: object) -> str:
    """The email of the account ``access_token`` authenticates."""
    me = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me.status_code == status.HTTP_200_OK, me.text
    return me.json()["email"]


async def test_registration_signs_the_new_account_in(
    browser_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    allow_registrations(monkeypatch, enabled=True)

    tokens = await register(browser_client)

    assert await email_of(browser_client, tokens["access_token"]) == EMAIL


async def test_registration_stores_a_refresh_token_that_rotates(
    browser_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    allow_registrations(monkeypatch, enabled=True)
    tokens = await register(browser_client)

    refreshed = await browser_client.post("/api/v1/auth/refresh")

    assert refreshed.status_code == status.HTTP_200_OK, refreshed.text
    assert refreshed.json()["refresh_token"] != tokens["refresh_token"]


async def test_the_registered_password_logs_in(
    browser_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    allow_registrations(monkeypatch, enabled=True)
    await register(browser_client)

    response = await browser_client.post(
        "/api/v1/auth/login", data={"username": EMAIL, "password": PASSWORD}
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert await email_of(browser_client, response.json()["access_token"]) == EMAIL


async def test_registration_is_refused_while_disabled(
    browser_client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    allow_registrations(monkeypatch, enabled=False)

    response = await browser_client.post(
        "/api/v1/users/register", json={"email": EMAIL, "password": PASSWORD}
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN, response.text
    stored = (await db_session.execute(select(User).filter_by(email=EMAIL))).scalar_one_or_none()
    assert stored is None
