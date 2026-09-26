"""Timing safety of AuthenticateUserUseCase: every login attempt verifies exactly one hash.

Not observable through the API, so it is pinned here at the password-service seam.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.identity.commands.authentication.authenticate_user_use_case import (
    AuthenticateUserUseCase,
)
from src.domain.identity.exceptions import InvalidCredentialsError
from src.infrastructure.identity.repositories.refresh_token_repository import (
    RefreshTokenRepository,
)
from src.infrastructure.identity.repositories.user_repository import UserRepository
from src.infrastructure.identity.services.password_service import hash_password
from src.infrastructure.identity.services.password_service_adapter import PasswordServiceAdapter
from src.infrastructure.identity.services.token_service_adapter import TokenServiceAdapter
from src.models import User


class RecordingPasswordService(PasswordServiceAdapter):
    """The real password service, recording the hash each verification ran against."""

    def __init__(self) -> None:
        self.verified_hashes: list[str] = []

    async def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        self.verified_hashes.append(hashed_password)
        return await super().verify_password(plain_password, hashed_password)


@pytest.fixture
def passwords() -> RecordingPasswordService:
    return RecordingPasswordService()


@pytest.fixture
def use_case(
    db_session: AsyncSession, passwords: RecordingPasswordService
) -> AuthenticateUserUseCase:
    return AuthenticateUserUseCase(
        user_repository=UserRepository(db_session),
        password_service=passwords,
        token_service=TokenServiceAdapter(),
        refresh_token_repository=RefreshTokenRepository(db_session),
    )


async def test_unknown_email_still_verifies_the_dummy_hash(
    use_case: AuthenticateUserUseCase, passwords: RecordingPasswordService
) -> None:
    """Skipping the hash would make account existence readable from latency."""
    with pytest.raises(InvalidCredentialsError):
        await use_case.authenticate("nobody@example.com", "password")

    assert passwords.verified_hashes == [passwords.get_dummy_hash()]


async def test_user_without_a_password_still_verifies_the_dummy_hash(
    use_case: AuthenticateUserUseCase, passwords: RecordingPasswordService, test_user: User
) -> None:
    """A passwordless account must not be a fast path either."""
    assert test_user.hashed_password is None

    with pytest.raises(InvalidCredentialsError):
        await use_case.authenticate(test_user.email, "password")

    assert passwords.verified_hashes == [passwords.get_dummy_hash()]


async def test_wrong_password_verifies_only_the_stored_hash(
    use_case: AuthenticateUserUseCase,
    passwords: RecordingPasswordService,
    db_session: AsyncSession,
    test_user: User,
) -> None:
    stored = await hash_password("the-right-password")
    test_user.hashed_password = stored
    await db_session.commit()

    with pytest.raises(InvalidCredentialsError):
        await use_case.authenticate(test_user.email, "wrong")

    assert passwords.verified_hashes == [stored]
