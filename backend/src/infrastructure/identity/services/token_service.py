"""Token creation and verification service."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from jwt import InvalidTokenError
from pydantic import BaseModel

from src.application.identity.dtos import (
    AccessTokenClaims,
    RefreshTokenClaims,
    TokenPairWithMetadata,
)
from src.config import get_settings

settings = get_settings()
SECRET_KEY = settings.SECRET_KEY
REFRESH_TOKEN_SECRET_KEY = settings.REFRESH_TOKEN_SECRET_KEY or SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_TYPE = "access"  # noqa: S105
REFRESH_TOKEN_TYPE = "refresh"  # noqa: S105
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS


class TokenWithRefresh(BaseModel):
    """Pydantic response model for HTTP API responses."""

    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


def create_access_token(user_id: int) -> str:
    """Create an access token for a user."""
    expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": str(user_id), "exp": expire, "type": ACCESS_TOKEN_TYPE}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: int, jti: str, expires_at: datetime) -> str:
    """Create a refresh token for a user with a jti claim."""
    to_encode = {"sub": str(user_id), "exp": expires_at, "type": REFRESH_TOKEN_TYPE, "jti": jti}
    return jwt.encode(to_encode, REFRESH_TOKEN_SECRET_KEY, algorithm=ALGORITHM)


def verify_access_token(token: str) -> AccessTokenClaims | None:
    """Verify an access token and return its claims if valid.

    The ``type`` claim has to say ``access`` rather than merely fail to say
    ``refresh``: other tokens signed with this key are all narrower.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != ACCESS_TOKEN_TYPE:
            return None
        user_id, expires_at = payload.get("sub"), payload.get("exp")
        if user_id is None or expires_at is None:
            return None
        return AccessTokenClaims(
            user_id=int(user_id),
            expires_at=datetime.fromtimestamp(expires_at, UTC),
        )
    except (InvalidTokenError, TypeError, ValueError, OSError, OverflowError):
        return None


def verify_refresh_token(token: str) -> RefreshTokenClaims | None:
    """Verify a refresh token and return claims if valid."""
    try:
        payload = jwt.decode(token, REFRESH_TOKEN_SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != REFRESH_TOKEN_TYPE:
            return None
        user_id = payload.get("sub")
        jti = payload.get("jti")
        if user_id is None or jti is None:
            return None
        return RefreshTokenClaims(user_id=int(user_id), jti=jti)
    except (InvalidTokenError, ValueError):
        return None


def create_token_pair(user_id: int, family_id: str) -> TokenPairWithMetadata:
    """Create a token pair (access + refresh) for a user."""
    jti = str(uuid.uuid4())
    refresh_token_expires_at = datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return reissue_token_pair(user_id, family_id, jti, refresh_token_expires_at)


def reissue_token_pair(
    user_id: int, family_id: str, jti: str, refresh_token_expires_at: datetime
) -> TokenPairWithMetadata:
    """Rebuild the pair for an already-issued refresh token.

    The refresh JWT is a pure function of these arguments, so a token whose jti
    and expiry are on record can be handed out again byte for byte without
    storing the token itself. That is what lets a client that lost a rotation
    response be answered with the very token it missed, rather than with a
    second one that would fork the family.
    """
    return TokenPairWithMetadata(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id, jti, refresh_token_expires_at),
        token_type="bearer",  # noqa: S106
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        jti=jti,
        family_id=family_id,
        refresh_token_expires_at=refresh_token_expires_at,
    )
