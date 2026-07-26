"""Tests for RefreshAccessTokenUseCase with token rotation."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.identity.commands.authentication.refresh_access_token_use_case import (
    RefreshAccessTokenUseCase,
)
from src.application.identity.dtos import RefreshTokenClaims, TokenPairWithMetadata
from src.domain.common.value_objects.ids import RefreshTokenId, UserId
from src.domain.identity.entities.refresh_token import RefreshToken
from src.domain.identity.entities.user import User
from src.domain.identity.exceptions import InvalidCredentialsError


def _make_user(user_id: int = 1) -> User:
    return User.create_with_id(
        id=UserId(user_id),
        email="test@example.com",
        hashed_password="hashed",
        created_at=MagicMock(),
        updated_at=MagicMock(),
    )


def _make_token_pair(family_id: str = "family-1") -> TokenPairWithMetadata:
    return TokenPairWithMetadata(
        access_token="new-access",
        refresh_token="new-refresh",
        token_type="bearer",
        expires_in=900,
        jti="new-jti",
        family_id=family_id,
        refresh_token_expires_at=datetime.now(UTC) + timedelta(days=30),
    )


def _make_refresh_token(
    jti: str = "old-jti",
    family_id: str = "family-1",
    revoked_at: datetime | None = None,
) -> RefreshToken:
    return RefreshToken.create_with_id(
        id=RefreshTokenId(1),
        jti=jti,
        user_id=UserId(1),
        family_id=family_id,
        revoked_at=revoked_at,
        expires_at=datetime.now(UTC) + timedelta(days=30),
        created_at=datetime.now(UTC),
    )


class TestRefreshAccessTokenUseCase:
    @pytest.fixture
    def user_repository(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def token_service(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def refresh_token_repository(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def use_case(
        self,
        user_repository: AsyncMock,
        token_service: MagicMock,
        refresh_token_repository: AsyncMock,
    ) -> RefreshAccessTokenUseCase:
        return RefreshAccessTokenUseCase(
            user_repository=user_repository,
            token_service=token_service,
            refresh_token_repository=refresh_token_repository,
        )

    async def test_successful_rotation(
        self,
        use_case: RefreshAccessTokenUseCase,
        user_repository: AsyncMock,
        token_service: MagicMock,
        refresh_token_repository: AsyncMock,
    ) -> None:
        claims = RefreshTokenClaims(user_id=1, jti="old-jti")
        token_service.verify_refresh_token.return_value = claims
        existing_token = _make_refresh_token()
        refresh_token_repository.find_by_jti.return_value = existing_token
        user = _make_user()
        user_repository.find_by_id.return_value = user
        token_pair = _make_token_pair()
        token_service.create_token_pair.return_value = token_pair
        refresh_token_repository.save.return_value = MagicMock()

        _, result = await use_case.refresh_token("old-token")

        assert result.access_token == "new-access"
        refresh_token_repository.revoke_family.assert_not_called()
        # revoke called for old token, save called for new token
        refresh_token_repository.revoke.assert_called_once_with(existing_token)
        refresh_token_repository.save.assert_called_once()
        new_saved = refresh_token_repository.save.call_args[0][0]
        assert new_saved.jti == "new-jti"
        assert new_saved.family_id == "family-1"

    async def test_invalid_jwt_raises_error(
        self, use_case: RefreshAccessTokenUseCase, token_service: MagicMock
    ) -> None:
        token_service.verify_refresh_token.return_value = None
        with pytest.raises(InvalidCredentialsError):
            await use_case.refresh_token("bad-token")

    async def test_unknown_jti_raises_error(
        self,
        use_case: RefreshAccessTokenUseCase,
        token_service: MagicMock,
        refresh_token_repository: AsyncMock,
    ) -> None:
        claims = RefreshTokenClaims(user_id=1, jti="unknown")
        token_service.verify_refresh_token.return_value = claims
        refresh_token_repository.find_by_jti.return_value = None
        with pytest.raises(InvalidCredentialsError):
            await use_case.refresh_token("some-token")

    async def test_revoked_token_triggers_family_revocation(
        self,
        use_case: RefreshAccessTokenUseCase,
        token_service: MagicMock,
        refresh_token_repository: AsyncMock,
    ) -> None:
        claims = RefreshTokenClaims(user_id=1, jti="revoked-jti")
        token_service.verify_refresh_token.return_value = claims
        revoked_token = _make_refresh_token(jti="revoked-jti", revoked_at=datetime.now(UTC))
        refresh_token_repository.find_by_jti.return_value = revoked_token
        with pytest.raises(InvalidCredentialsError):
            await use_case.refresh_token("revoked-token")
        refresh_token_repository.revoke_family.assert_called_once_with("family-1")

    async def test_user_not_found_raises_error(
        self,
        use_case: RefreshAccessTokenUseCase,
        token_service: MagicMock,
        refresh_token_repository: AsyncMock,
        user_repository: AsyncMock,
    ) -> None:
        claims = RefreshTokenClaims(user_id=1, jti="old-jti")
        token_service.verify_refresh_token.return_value = claims
        refresh_token_repository.find_by_jti.return_value = _make_refresh_token()
        user_repository.find_by_id.return_value = None
        with pytest.raises(InvalidCredentialsError):
            await use_case.refresh_token("some-token")

    async def test_lazy_cleanup_called(
        self,
        use_case: RefreshAccessTokenUseCase,
        user_repository: AsyncMock,
        token_service: MagicMock,
        refresh_token_repository: AsyncMock,
    ) -> None:
        claims = RefreshTokenClaims(user_id=1, jti="old-jti")
        token_service.verify_refresh_token.return_value = claims
        refresh_token_repository.find_by_jti.return_value = _make_refresh_token()
        user_repository.find_by_id.return_value = _make_user()
        token_service.create_token_pair.return_value = _make_token_pair()
        refresh_token_repository.save.return_value = MagicMock()
        await use_case.refresh_token("token")
        refresh_token_repository.delete_expired_for_user.assert_called_once_with(UserId(1))
