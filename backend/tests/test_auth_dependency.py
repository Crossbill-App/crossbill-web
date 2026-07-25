"""Tests for get_current_user, which the shared ``client`` fixture overrides away."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.infrastructure.identity.services.token_service import create_access_token
from src.main import app
from src.models import User


@pytest.fixture
async def real_auth_client(
    db_session: AsyncSession, test_user: User
) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def test_real_get_current_user(real_auth_client: AsyncClient, test_user: User) -> None:
    token = create_access_token(test_user.id)
    response = await real_auth_client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["email"] == test_user.email


async def test_real_get_current_user_rejects_unknown_user(
    real_auth_client: AsyncClient,
) -> None:
    token = create_access_token(9999)
    response = await real_auth_client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401, response.text
