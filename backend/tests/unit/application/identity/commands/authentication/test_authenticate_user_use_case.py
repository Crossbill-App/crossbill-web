"""Tests for AuthenticateUserUseCase with token rotation."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.identity.commands.authentication.authenticate_user_use_case import (
    AuthenticateUserUseCase,
)
from src.application.identity.dtos import TokenPairWithMetadata
from src.domain.common.value_objects.ids import UserId
from src.domain.identity.entities.user import User
from src.domain.identity.exceptions import InvalidCredentialsError
from tests.unit.application.identity.commands.conftest import make_token_pair


def _make_user(user_id: int = 1) -> User:
    return User.create_with_id(
        id=UserId(user_id),
        email="test@example.com",
        hashed_password="hashed",
        created_at=MagicMock(),
        updated_at=MagicMock(),
    )


class TestAuthenticateUserUseCase:
    @pytest.fixture
    def use_case(
        self,
        user_repository: AsyncMock,
        password_service: MagicMock,
        token_service: MagicMock,
        refresh_token_repository: AsyncMock,
    ) -> AuthenticateUserUseCase:
        return AuthenticateUserUseCase(
            user_repository=user_repository,
            password_service=password_service,
            token_service=token_service,
            refresh_token_repository=refresh_token_repository,
        )

    @pytest.fixture
    def _successful_auth_setup(
        self,
        user_repository: AsyncMock,
        password_service: MagicMock,
        token_service: MagicMock,
        refresh_token_repository: AsyncMock,
    ) -> TokenPairWithMetadata:
        user = _make_user()
        user_repository.find_by_email.return_value = user
        password_service.verify_password.return_value = True
        token_pair = make_token_pair()
        token_service.create_token_pair.return_value = token_pair
        refresh_token_repository.save.return_value = MagicMock()
        return token_pair

    async def test_authenticate_persists_refresh_token(
        self,
        use_case: AuthenticateUserUseCase,
        token_service: MagicMock,
        refresh_token_repository: AsyncMock,
        _successful_auth_setup: TokenPairWithMetadata,
    ) -> None:
        _, result = await use_case.authenticate("test@example.com", "password")

        assert result.access_token == "access"
        assert result.jti == "test-jti"

        token_service.create_token_pair.assert_called_once()
        call_args = token_service.create_token_pair.call_args
        assert call_args[0][0] == 1

        refresh_token_repository.save.assert_called_once()
        saved_token = refresh_token_repository.save.call_args[0][0]
        assert saved_token.jti == "test-jti"
        assert saved_token.family_id == "test-family"
        assert saved_token.user_id == UserId(1)

    async def test_unknown_email_still_verifies_a_hash(
        self,
        use_case: AuthenticateUserUseCase,
        user_repository: AsyncMock,
        password_service: MagicMock,
    ) -> None:
        """Skipping the hash would make account existence readable from latency."""
        user_repository.find_by_email.return_value = None

        with pytest.raises(InvalidCredentialsError):
            await use_case.authenticate("nobody@example.com", "password")

        password_service.verify_password.assert_awaited_once_with(
            "password", password_service.get_dummy_hash()
        )

    async def test_wrong_password_verifies_the_same_number_of_hashes(
        self,
        use_case: AuthenticateUserUseCase,
        user_repository: AsyncMock,
        password_service: MagicMock,
    ) -> None:
        user_repository.find_by_email.return_value = _make_user()

        with pytest.raises(InvalidCredentialsError):
            await use_case.authenticate("test@example.com", "wrong")

        password_service.verify_password.assert_awaited_once_with("wrong", "hashed")

    async def test_user_without_a_password_still_verifies_a_hash(
        self,
        use_case: AuthenticateUserUseCase,
        user_repository: AsyncMock,
        password_service: MagicMock,
    ) -> None:
        """A passwordless account must not be a fast path either."""
        user = _make_user()
        user.hashed_password = None
        user_repository.find_by_email.return_value = user

        with pytest.raises(InvalidCredentialsError):
            await use_case.authenticate("test@example.com", "password")

        password_service.verify_password.assert_awaited_once_with(
            "password", password_service.get_dummy_hash()
        )
