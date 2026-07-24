"""Tests for UpdateUserUseCase session revocation on password change."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.identity.dtos import RefreshTokenClaims
from src.application.identity.use_cases.update_user_use_case import UpdateUserUseCase
from src.domain.common.value_objects.ids import RefreshTokenId, UserId
from src.domain.identity.entities.refresh_token import RefreshToken
from src.domain.identity.entities.user import User
from src.domain.identity.exceptions import PasswordVerificationError

USER_ID = 1
CURRENT_FAMILY = "family-of-the-calling-session"


def _make_user() -> User:
    return User(id=UserId(USER_ID), email="reader@example.com", hashed_password="stored-hash")


def _make_refresh_token(user_id: int = USER_ID, family_id: str = CURRENT_FAMILY) -> RefreshToken:
    return RefreshToken(
        id=RefreshTokenId(10),
        jti="jti-of-the-calling-session",
        user_id=UserId(user_id),
        family_id=family_id,
        expires_at=datetime.now(UTC) + timedelta(days=30),
        revoked_at=None,
    )


class TestUpdateUserUseCase:
    @pytest.fixture
    def user_repository(self) -> AsyncMock:
        repository = AsyncMock()
        repository.find_by_id.return_value = _make_user()
        repository.save.side_effect = lambda user: user
        return repository

    @pytest.fixture
    def password_service(self) -> MagicMock:
        service = MagicMock()
        service.hash_password = AsyncMock(return_value="new-hash")
        service.verify_password = AsyncMock(return_value=True)
        return service

    @pytest.fixture
    def token_service(self) -> MagicMock:
        service = MagicMock()
        service.verify_refresh_token.return_value = RefreshTokenClaims(
            user_id=USER_ID, jti="jti-of-the-calling-session"
        )
        return service

    @pytest.fixture
    def refresh_token_repository(self) -> AsyncMock:
        repository = AsyncMock()
        repository.find_by_jti.return_value = _make_refresh_token()
        return repository

    @pytest.fixture
    def use_case(
        self,
        user_repository: AsyncMock,
        password_service: MagicMock,
        token_service: MagicMock,
        refresh_token_repository: AsyncMock,
    ) -> UpdateUserUseCase:
        return UpdateUserUseCase(
            user_repository=user_repository,
            password_service=password_service,
            token_service=token_service,
            refresh_token_repository=refresh_token_repository,
        )

    async def test_password_change_revokes_other_sessions(
        self, use_case: UpdateUserUseCase, refresh_token_repository: AsyncMock
    ) -> None:
        await use_case.update_user(
            user_id=USER_ID,
            current_password="old",
            new_password="new-password",
            current_refresh_token="a-valid-refresh-token",
        )

        refresh_token_repository.revoke_all_for_user.assert_awaited_once_with(
            UserId(USER_ID), except_family_id=CURRENT_FAMILY
        )

    async def test_password_change_without_a_cookie_revokes_everything(
        self, use_case: UpdateUserUseCase, refresh_token_repository: AsyncMock
    ) -> None:
        await use_case.update_user(
            user_id=USER_ID, current_password="old", new_password="new-password"
        )

        refresh_token_repository.revoke_all_for_user.assert_awaited_once_with(
            UserId(USER_ID), except_family_id=None
        )

    async def test_another_users_refresh_token_is_not_spared(
        self,
        use_case: UpdateUserUseCase,
        refresh_token_repository: AsyncMock,
    ) -> None:
        refresh_token_repository.find_by_jti.return_value = _make_refresh_token(
            user_id=USER_ID + 1, family_id="someone-elses-family"
        )

        await use_case.update_user(
            user_id=USER_ID,
            current_password="old",
            new_password="new-password",
            current_refresh_token="a-refresh-token-for-another-user",
        )

        refresh_token_repository.revoke_all_for_user.assert_awaited_once_with(
            UserId(USER_ID), except_family_id=None
        )

    async def test_unverifiable_refresh_token_revokes_everything(
        self,
        use_case: UpdateUserUseCase,
        token_service: MagicMock,
        refresh_token_repository: AsyncMock,
    ) -> None:
        token_service.verify_refresh_token.return_value = None

        await use_case.update_user(
            user_id=USER_ID,
            current_password="old",
            new_password="new-password",
            current_refresh_token="a-forged-refresh-token",
        )

        refresh_token_repository.revoke_all_for_user.assert_awaited_once_with(
            UserId(USER_ID), except_family_id=None
        )

    async def test_email_change_leaves_sessions_alone(
        self, use_case: UpdateUserUseCase, refresh_token_repository: AsyncMock
    ) -> None:
        await use_case.update_user(user_id=USER_ID, email="new@example.com")

        refresh_token_repository.revoke_all_for_user.assert_not_awaited()

    async def test_wrong_current_password_revokes_nothing(
        self,
        use_case: UpdateUserUseCase,
        password_service: MagicMock,
        refresh_token_repository: AsyncMock,
    ) -> None:
        password_service.verify_password = AsyncMock(return_value=False)

        with pytest.raises(PasswordVerificationError):
            await use_case.update_user(
                user_id=USER_ID, current_password="wrong", new_password="new-password"
            )

        refresh_token_repository.revoke_all_for_user.assert_not_awaited()
