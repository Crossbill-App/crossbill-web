"""Shared doubles for the identity command use cases.

Authentication, registration and logout all take the same four collaborators,
so the mocks live here rather than being re-declared per test class.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.identity.dtos import TokenPairWithMetadata


def make_token_pair() -> TokenPairWithMetadata:
    """The token pair the token service hands back on a successful login."""
    return TokenPairWithMetadata(
        access_token="access",
        refresh_token="refresh",
        token_type="bearer",
        expires_in=900,
        jti="test-jti",
        family_id="test-family",
        refresh_token_expires_at=datetime.now(UTC) + timedelta(days=30),
    )


@pytest.fixture
def user_repository() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def password_service() -> MagicMock:
    # Hashing is awaited (it runs on a worker thread); get_dummy_hash is not.
    service = MagicMock()
    service.hash_password = AsyncMock(return_value="hashed")
    service.verify_password = AsyncMock(return_value=False)
    return service


@pytest.fixture
def token_service() -> MagicMock:
    return MagicMock()


@pytest.fixture
def refresh_token_repository() -> AsyncMock:
    return AsyncMock()
