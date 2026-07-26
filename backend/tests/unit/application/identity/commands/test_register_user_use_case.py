"""Tests for RegisterUserUseCase with token rotation."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.application.identity.commands.register_user_use_case import RegisterUserUseCase
from src.application.identity.dtos import TokenPairWithMetadata
from src.domain.common.value_objects.ids import UserId
from src.domain.identity.entities.user import User


def _make_user(user_id: int = 1) -> User:
    return User.create_with_id(
        id=UserId(user_id),
        email="new@example.com",
        hashed_password="hashed",
        created_at=MagicMock(),
        updated_at=MagicMock(),
    )


def _make_token_pair() -> TokenPairWithMetadata:
    return TokenPairWithMetadata(
        access_token="access",
        refresh_token="refresh",
        token_type="bearer",
        expires_in=900,
        jti="test-jti",
        family_id="test-family",
        refresh_token_expires_at=datetime.now(UTC) + timedelta(days=30),
    )


class TestRegisterUserUseCase:
    @pytest.fixture
    def user_repository(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def password_service(self) -> MagicMock:
        # Hashing is awaited (it runs on a worker thread); get_dummy_hash is not.
        service = MagicMock()
        service.hash_password = AsyncMock(return_value="hashed")
        service.verify_password = AsyncMock(return_value=False)
        return service

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
        password_service: MagicMock,
        token_service: MagicMock,
        refresh_token_repository: AsyncMock,
    ) -> RegisterUserUseCase:
        return RegisterUserUseCase(
            user_repository=user_repository,
            password_service=password_service,
            token_service=token_service,
            refresh_token_repository=refresh_token_repository,
        )

    @pytest.fixture
    def _successful_register_setup(
        self,
        user_repository: AsyncMock,
        password_service: MagicMock,
        token_service: MagicMock,
        refresh_token_repository: AsyncMock,
    ) -> TokenPairWithMetadata:
        password_service.hash_password.return_value = "hashed"
        user = _make_user()
        user_repository.save.return_value = user
        token_pair = _make_token_pair()
        token_service.create_token_pair.return_value = token_pair
        refresh_token_repository.save.return_value = MagicMock()
        return token_pair

    @patch(
        "src.application.identity.commands.register_user_use_case.is_user_registrations_enabled",
        return_value=True,
    )
    async def test_register_persists_refresh_token(
        self,
        _mock_flag: MagicMock,
        use_case: RegisterUserUseCase,
        refresh_token_repository: AsyncMock,
        _successful_register_setup: TokenPairWithMetadata,
    ) -> None:
        await use_case.register_user("new@example.com", "password")

        refresh_token_repository.save.assert_called_once()
        saved = refresh_token_repository.save.call_args[0][0]
        assert saved.jti == "test-jti"
        assert saved.family_id == "test-family"
        assert saved.user_id == UserId(1)
