"""RefreshToken entity for token rotation tracking."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from src.domain.common.entity import Entity
from src.domain.common.value_objects.ids import RefreshTokenId, UserId


@dataclass
class RefreshToken(Entity[RefreshTokenId]):
    """
    Tracks a refresh token for rotation and replay detection.

    Each token belongs to a family (one per login session).
    When rotated, the old token is revoked and a new one is created
    in the same family. Replaying a revoked token revokes the entire family.

    A rotated token remembers its replacement in ``replaced_by_jti``. A token
    revoked for any other reason — logout, a password change — leaves it unset,
    which is what keeps those revocations final.
    """

    id: RefreshTokenId
    jti: str
    user_id: UserId
    family_id: str
    revoked_at: datetime | None
    expires_at: datetime
    created_at: datetime | None = None
    replaced_by_jti: str | None = None

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def is_expired(self) -> bool:
        return self.expires_at < datetime.now(UTC)

    def revoke(self) -> None:
        self.revoked_at = datetime.now(UTC)

    def rotate_to(self, successor_jti: str) -> None:
        """Spend this token in exchange for ``successor_jti``."""
        self.revoked_at = datetime.now(UTC)
        self.replaced_by_jti = successor_jti

    def successor_within(self, grace: timedelta) -> str | None:
        """The jti this token was exchanged for, while that exchange is recent.

        Rotation cannot be atomic across the network: the server spends the old
        token before the new one has arrived anywhere. Re-presenting the spent
        token within ``grace`` is therefore far more likely to be the same
        client retrying than an attacker replaying, and answering with the
        replacement converges both on one token. Past the window there is no
        innocent explanation left, so the caller treats it as replay.

        Returns ``None`` for a token that was revoked rather than rotated.
        """
        if self.replaced_by_jti is None or self.revoked_at is None:
            return None
        if datetime.now(UTC) - self.revoked_at > grace:
            return None
        return self.replaced_by_jti

    @classmethod
    def create(
        cls,
        jti: str,
        user_id: UserId,
        family_id: str,
        expires_at: datetime,
    ) -> "RefreshToken":
        return cls(
            id=RefreshTokenId.generate(),
            jti=jti,
            user_id=user_id,
            family_id=family_id,
            revoked_at=None,
            expires_at=expires_at,
        )

    @classmethod
    def create_with_id(
        cls,
        id: RefreshTokenId,
        jti: str,
        user_id: UserId,
        family_id: str,
        revoked_at: datetime | None,
        expires_at: datetime,
        created_at: datetime,
        replaced_by_jti: str | None = None,
    ) -> "RefreshToken":
        return cls(
            id=id,
            jti=jti,
            user_id=user_id,
            family_id=family_id,
            revoked_at=revoked_at,
            expires_at=expires_at,
            created_at=created_at,
            replaced_by_jti=replaced_by_jti,
        )
