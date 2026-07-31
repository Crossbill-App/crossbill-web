"""Tests for RefreshToken domain entity."""

from datetime import UTC, datetime, timedelta

from src.domain.common.value_objects.ids import RefreshTokenId, UserId
from src.domain.identity.entities.refresh_token import RefreshToken


def _create(**overrides: str | UserId | datetime) -> RefreshToken:
    defaults = {
        "jti": "550e8400-e29b-41d4-a716-446655440000",
        "user_id": UserId(1),
        "family_id": "660e8400-e29b-41d4-a716-446655440000",
        "expires_at": datetime.now(UTC) + timedelta(days=30),
    }
    defaults.update(overrides)
    return RefreshToken.create(**defaults)  # type: ignore[arg-type]


class TestRefreshTokenCreate:
    def test_create_sets_fields(self) -> None:
        token = _create()
        assert token.id == RefreshTokenId(0)
        assert token.jti == "550e8400-e29b-41d4-a716-446655440000"
        assert token.user_id == UserId(1)
        assert token.family_id == "660e8400-e29b-41d4-a716-446655440000"
        assert token.revoked_at is None

    def test_create_with_id_reconstitutes(self) -> None:
        now = datetime.now(UTC)
        token = RefreshToken.create_with_id(
            id=RefreshTokenId(42),
            jti="abc",
            user_id=UserId(1),
            family_id="def",
            revoked_at=None,
            expires_at=now + timedelta(days=30),
            created_at=now,
        )
        assert token.id == RefreshTokenId(42)
        assert token.jti == "abc"
        assert token.created_at == now


class TestRefreshTokenRevoke:
    def test_revoke_sets_revoked_at(self) -> None:
        token = _create()
        assert token.revoked_at is None
        token.revoke()
        assert token.revoked_at is not None

    def test_is_revoked(self) -> None:
        token = _create()
        assert not token.is_revoked
        token.revoke()
        assert token.is_revoked

    def test_is_expired(self) -> None:
        token = _create(expires_at=datetime.now(UTC) - timedelta(hours=1))
        assert token.is_expired

    def test_is_not_expired(self) -> None:
        token = _create(expires_at=datetime.now(UTC) + timedelta(days=30))
        assert not token.is_expired


class TestRefreshTokenSuccessorWithin:
    GRACE = timedelta(seconds=60)

    def test_a_live_token_has_no_successor(self) -> None:
        assert _create().successor_within(self.GRACE) is None

    def test_a_rotated_token_names_its_replacement(self) -> None:
        token = _create()
        token.rotate_to("successor-jti")
        assert token.successor_within(self.GRACE) == "successor-jti"

    def test_a_token_revoked_outright_names_nothing(self) -> None:
        """Logout and password changes revoke without rotating, and must stay final."""
        token = _create()
        token.revoke()
        assert token.successor_within(self.GRACE) is None

    def test_an_old_rotation_names_nothing(self) -> None:
        token = _create()
        token.rotate_to("successor-jti")
        token.revoked_at = datetime.now(UTC) - timedelta(minutes=5)
        assert token.successor_within(self.GRACE) is None

    def test_a_zero_window_names_nothing(self) -> None:
        """Setting the grace to zero restores strict single-use rotation."""
        token = _create()
        token.rotate_to("successor-jti")
        token.revoked_at = datetime.now(UTC) - timedelta(seconds=1)
        assert token.successor_within(timedelta(0)) is None
