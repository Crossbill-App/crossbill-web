"""The credential a navigator's iframe can carry: one user, one book, short-lived.

Nothing stores or revokes such a token, so its scope and its short life are the
whole of what bounds it.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from jwt import InvalidTokenError

from src.application.web_reader.dtos import PublicationToken
from src.config import get_settings

settings = get_settings()
PUBLICATION_TOKEN_SECRET_KEY = settings.PUBLICATION_TOKEN_SECRET_KEY or settings.SECRET_KEY
ALGORITHM = "HS256"
PUBLICATION_TOKEN_TYPE = "publication"  # noqa: S105

# Every book's cookie carries this name; their paths are what tell them apart.
PUBLICATION_COOKIE_NAME = "publication_access"

PUBLICATION_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES


@dataclass(frozen=True)
class PublicationTokenClaims:
    """Who a verified publication token is for, and which book it opens."""

    user_id: int
    book_id: int


def create_publication_token(user_id: int, book_id: int, not_after: datetime) -> PublicationToken:
    """Sign a token letting one user read one book, until ``not_after`` at the latest.

    Nothing revokes one of these once signed, so a token minted from a
    nearly-spent access token inherits what is left of it rather than restarting
    the clock on a session that may have just ended.
    """
    now = datetime.now(UTC)
    # The TTL binds only tokens minted before it was lowered: an access token
    # still carries the `exp` that the setting in force at its own minting gave it.
    expire = min(now + timedelta(minutes=PUBLICATION_TOKEN_EXPIRE_MINUTES), not_after)
    claims = {
        "sub": str(user_id),
        "book": str(book_id),
        "exp": expire,
        "type": PUBLICATION_TOKEN_TYPE,
    }
    return PublicationToken(
        value=jwt.encode(claims, PUBLICATION_TOKEN_SECRET_KEY, algorithm=ALGORITHM),
        expires_in=max(int((expire - now).total_seconds()), 0),
    )


def verify_publication_token(token: str) -> PublicationTokenClaims | None:
    """Verify a publication token and return its claims, or ``None`` if it is no good.

    That the book named is the book being asked for is the caller's check: this
    says the token is genuine, not that it is genuine *here*.
    """
    try:
        payload = jwt.decode(token, PUBLICATION_TOKEN_SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != PUBLICATION_TOKEN_TYPE:
            return None
        user_id, book_id = payload.get("sub"), payload.get("book")
        if user_id is None or book_id is None:
            return None
        return PublicationTokenClaims(user_id=int(user_id), book_id=int(book_id))
    except (InvalidTokenError, TypeError, ValueError, OSError, OverflowError):
        return None
