"""Tests for bulk refresh-token revocation against the database."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.common.value_objects.ids import UserId
from src.domain.identity.entities.refresh_token import RefreshToken
from src.infrastructure.identity.orm.user_model import User
from src.infrastructure.identity.repositories.refresh_token_repository import (
    RefreshTokenRepository,
)


async def _save_token(
    repository: RefreshTokenRepository, user_id: int, jti: str, family_id: str
) -> None:
    await repository.save(
        RefreshToken.create(
            jti=jti,
            user_id=UserId(user_id),
            family_id=family_id,
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
    )


async def test_revoke_all_for_user_spares_the_named_family(
    db_session: AsyncSession, test_user: User
) -> None:
    repository = RefreshTokenRepository(db_session)
    user_id = test_user.id
    await _save_token(repository, user_id, "jti-current", "family-current")
    await _save_token(repository, user_id, "jti-phone", "family-phone")
    await _save_token(repository, user_id, "jti-ereader", "family-ereader")

    await repository.revoke_all_for_user(UserId(user_id), except_family_id="family-current")

    current = await repository.find_by_jti("jti-current")
    phone = await repository.find_by_jti("jti-phone")
    ereader = await repository.find_by_jti("jti-ereader")
    assert current is not None
    assert not current.is_revoked
    assert phone is not None
    assert phone.is_revoked
    assert ereader is not None
    assert ereader.is_revoked


async def test_revoke_all_for_user_without_exception_revokes_every_session(
    db_session: AsyncSession, test_user: User
) -> None:
    repository = RefreshTokenRepository(db_session)
    user_id = test_user.id
    await _save_token(repository, user_id, "jti-a", "family-a")
    await _save_token(repository, user_id, "jti-b", "family-b")

    await repository.revoke_all_for_user(UserId(user_id))

    for jti in ("jti-a", "jti-b"):
        token = await repository.find_by_jti(jti)
        assert token is not None
        assert token.is_revoked


async def test_revoke_all_for_user_leaves_other_users_alone(
    db_session: AsyncSession, test_user: User
) -> None:
    repository = RefreshTokenRepository(db_session)
    other_user = User(email="someone-else@example.com", hashed_password="stored-hash")
    db_session.add(other_user)
    await db_session.commit()

    await _save_token(repository, test_user.id, "jti-mine", "family-mine")
    await _save_token(repository, other_user.id, "jti-theirs", "family-theirs")

    await repository.revoke_all_for_user(UserId(test_user.id))

    theirs = await repository.find_by_jti("jti-theirs")
    assert theirs is not None
    assert not theirs.is_revoked
