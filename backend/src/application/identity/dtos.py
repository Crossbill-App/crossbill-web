"""Application-layer DTOs for identity module."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AccessTokenClaims:
    """Claims extracted from a verified access token JWT.

    The expiry is carried alongside the user because a credential minted during
    a request may not outlive the one that bought it: the web reader's
    publication cookie (#737) is capped by this.
    """

    user_id: int
    expires_at: datetime


@dataclass(frozen=True)
class RefreshTokenClaims:
    """Claims extracted from a verified refresh token JWT."""

    user_id: int
    jti: str


@dataclass(frozen=True)
class TokenPairWithMetadata:
    """Token pair with metadata needed for persistence."""

    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    jti: str
    family_id: str
    refresh_token_expires_at: datetime
