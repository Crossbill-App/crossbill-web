"""End-to-end checks that a password change evicts existing sessions."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.common.value_objects.ids import UserId
from src.domain.identity.entities.refresh_token import RefreshToken
from src.infrastructure.identity.orm.user_model import User
from src.infrastructure.identity.repositories.refresh_token_repository import (
    RefreshTokenRepository,
)
from src.infrastructure.identity.services.password_service import hash_password


async def test_password_change_revokes_a_stolen_refresh_token(
    client: AsyncClient, db_session: AsyncSession, test_user: User
) -> None:
    test_user.hashed_password = await hash_password("old-password")
    await db_session.commit()

    repository = RefreshTokenRepository(db_session)
    await repository.save(
        RefreshToken.create(
            jti="jti-stolen",
            user_id=UserId(test_user.id),
            family_id="family-stolen",
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
    )

    # Re-load: the commits above leave test_user's attributes expired, and the
    # auth fixture reads them while solving dependencies.
    await db_session.refresh(test_user)

    response = await client.post(
        "/api/v1/users/me",
        json={"current_password": "old-password", "new_password": "a-new-password"},
    )

    assert response.status_code == 200
    stolen = await repository.find_by_jti("jti-stolen")
    assert stolen is not None
    assert stolen.is_revoked


async def test_wrong_current_password_leaves_sessions_intact(
    client: AsyncClient, db_session: AsyncSession, test_user: User
) -> None:
    test_user.hashed_password = await hash_password("old-password")
    await db_session.commit()

    repository = RefreshTokenRepository(db_session)
    await repository.save(
        RefreshToken.create(
            jti="jti-live",
            user_id=UserId(test_user.id),
            family_id="family-live",
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
    )

    await db_session.refresh(test_user)

    response = await client.post(
        "/api/v1/users/me",
        json={"current_password": "wrong-password", "new_password": "a-new-password"},
    )

    assert response.status_code == 401
    live = await repository.find_by_jti("jti-live")
    assert live is not None
    assert not live.is_revoked


async def test_refresh_cookie_does_not_reach_the_profile_endpoint(
    client: AsyncClient, db_session: AsyncSession, test_user: User
) -> None:
    """The cookie is scoped to /api/v1/auth, so /users/me can never read it."""
    client.cookies.set("refresh_token", "a-token", domain="test", path="/api/v1/auth")

    request = client.build_request("POST", "/api/v1/users/me", json={})

    assert "cookie" not in {name.lower() for name in request.headers}
