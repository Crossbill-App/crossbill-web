"""The short-lived credential a navigator's iframe can carry (ADR-0004, amended).

``@readium/navigator`` loads each resource of a publication straight into an
iframe, and an iframe load sends cookies and nothing else -- not the SPA's
access token, which lives in memory precisely so that nothing else can reach it.
So the reader is given a second credential that a browser will attach on its
own, and this module is what makes that credential safe to hand out: it is
signed like an access token, it names exactly one user and one book, and it
never outlives the access token that bought it.

It is deliberately not a session: nothing is stored, nothing is revoked, and a
token is a pure function of its claims. What bounds the damage is its scope --
one book, read-only, for as long as the Bearer token that minted it would have
lasted anyway.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from jwt import InvalidTokenError

from src.config import get_settings

settings = get_settings()
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"

# The ``type`` claim that separates this from an access token signed with the
# same key. ``verify_access_token`` requires its own type for the same reason:
# neither token may be spent as the other.
PUBLICATION_TOKEN_TYPE = "publication"  # noqa: S105

# The cookie's name. Two books' cookies share it and are told apart by their
# paths, which is what makes a browser send exactly the one that belongs to the
# book being read.
PUBLICATION_COOKIE_NAME = "publication_access"

# The ceiling: as long as a fresh access token and no longer. The reader
# re-mints on the same schedule it already refreshes its access token on.
PUBLICATION_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES


@dataclass(frozen=True)
class PublicationTokenClaims:
    """Who a verified publication token is for, and which book it opens."""

    user_id: int
    book_id: int


@dataclass(frozen=True)
class PublicationToken:
    """A signed publication token, and the seconds it has to live.

    The lifetime comes back with the token because it is not a constant: it is
    whatever was left of the credential that bought this one.
    """

    value: str
    expires_in: int


def create_publication_token(user_id: int, book_id: int, not_after: datetime) -> PublicationToken:
    """Sign a token letting one user read one book's publication until ``not_after`` at the latest.

    ``not_after`` is the expiry of the access token being spent to mint this
    one, and it is a hard ceiling on top of the TTL. Nothing revokes a
    publication token once signed, so a token minted from a nearly-spent Bearer
    must inherit what is left of it rather than start the clock again -- else a
    session that has ended (password changed, refresh family revoked) buys
    itself another quarter of an hour of reading on the way out.
    """
    now = datetime.now(UTC)
    expire = min(now + timedelta(minutes=PUBLICATION_TOKEN_EXPIRE_MINUTES), not_after)
    claims = {
        "sub": str(user_id),
        "book": str(book_id),
        "exp": expire,
        "type": PUBLICATION_TOKEN_TYPE,
    }
    return PublicationToken(
        value=jwt.encode(claims, SECRET_KEY, algorithm=ALGORITHM),
        expires_in=max(int((expire - now).total_seconds()), 0),
    )


def verify_publication_token(token: str) -> PublicationTokenClaims | None:
    """Verify a publication token and return its claims, or ``None`` if it is no good.

    ``None`` covers every way a token can fail to be one: a bad signature, an
    expired ``exp``, a token of another type, and claims that do not name both a
    user and a book. The caller still has to check that the book named is the
    book being asked for -- this says the token is genuine, not that it is
    genuine *here*.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except InvalidTokenError:
        return None
    if payload.get("type") != PUBLICATION_TOKEN_TYPE:
        return None
    user_id, book_id = payload.get("sub"), payload.get("book")
    if user_id is None or book_id is None:
        return None
    try:
        return PublicationTokenClaims(user_id=int(user_id), book_id=int(book_id))
    except ValueError:
        return None
