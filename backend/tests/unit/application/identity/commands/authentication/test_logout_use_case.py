"""Tests for LogoutUseCase."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.identity.commands.authentication.logout_use_case import LogoutUseCase
from src.application.identity.dtos import RefreshTokenClaims
from src.domain.common.value_objects.ids import RefreshTokenId, UserId
from src.domain.identity.entities.refresh_token import RefreshToken


class TestLogoutUseCase:
    @pytest.fixture
    def token_service(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def refresh_token_repository(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def use_case(
        self, token_service: MagicMock, refresh_token_repository: AsyncMock
    ) -> LogoutUseCase:
        return LogoutUseCase(
            token_service=token_service,
            refresh_token_repository=refresh_token_repository,
        )

    async def test_logout_revokes_family(
        self,
        use_case: LogoutUseCase,
        token_service: MagicMock,
        refresh_token_repository: AsyncMock,
    ) -> None:
        claims = RefreshTokenClaims(user_id=1, jti="test-jti")
        token_service.verify_refresh_token.return_value = claims
        token = RefreshToken.create_with_id(
            id=RefreshTokenId(1),
            jti="test-jti",
            user_id=UserId(1),
            family_id="family-1",
            revoked_at=None,
            expires_at=datetime.now(UTC) + timedelta(days=30),
            created_at=datetime.now(UTC),
        )
        refresh_token_repository.find_by_jti.return_value = token
        await use_case.logout("refresh-token-string")
        refresh_token_repository.revoke_family.assert_called_once_with("family-1")

    async def test_logout_with_invalid_token_succeeds_silently(
        self,
        use_case: LogoutUseCase,
        token_service: MagicMock,
        refresh_token_repository: AsyncMock,
    ) -> None:
        token_service.verify_refresh_token.return_value = None
        await use_case.logout("bad-token")
        refresh_token_repository.revoke_family.assert_not_called()

    async def test_logout_with_none_token_succeeds_silently(
        self,
        use_case: LogoutUseCase,
        token_service: MagicMock,
        refresh_token_repository: AsyncMock,
    ) -> None:
        await use_case.logout(None)
        token_service.verify_refresh_token.assert_not_called()
        refresh_token_repository.revoke_family.assert_not_called()

    async def test_logout_with_unknown_jti_succeeds_silently(
        self,
        use_case: LogoutUseCase,
        token_service: MagicMock,
        refresh_token_repository: AsyncMock,
    ) -> None:
        claims = RefreshTokenClaims(user_id=1, jti="unknown")
        token_service.verify_refresh_token.return_value = claims
        refresh_token_repository.find_by_jti.return_value = None
        await use_case.logout("some-token")
        refresh_token_repository.revoke_family.assert_not_called()
