"""Tests for UpdateUserUseCase session revocation on password change."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.identity.use_cases.update_user_use_case import UpdateUserUseCase
from src.domain.common.value_objects.ids import UserId
from src.domain.identity.entities.user import User
from src.domain.identity.exceptions import PasswordVerificationError

USER_ID = 1


def _make_user() -> User:
    return User(id=UserId(USER_ID), email="reader@example.com", hashed_password="stored-hash")


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
    def refresh_token_repository(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def use_case(
        self,
        user_repository: AsyncMock,
        password_service: MagicMock,
        refresh_token_repository: AsyncMock,
    ) -> UpdateUserUseCase:
        return UpdateUserUseCase(
            user_repository=user_repository,
            password_service=password_service,
            refresh_token_repository=refresh_token_repository,
        )

    async def test_password_change_revokes_every_session(
        self, use_case: UpdateUserUseCase, refresh_token_repository: AsyncMock
    ) -> None:
        """Including the caller's own — the cookie identifying it cannot reach this endpoint."""
        await use_case.update_user(
            user_id=USER_ID, current_password="old", new_password="new-password"
        )

        refresh_token_repository.revoke_all_for_user.assert_awaited_once_with(UserId(USER_ID))

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
