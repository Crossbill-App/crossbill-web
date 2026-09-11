"""Application-layer DTOs for the web reader module."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PublicationToken:
    """A signed publication token and the seconds it has to live.

    The lifetime travels with the token because it is not the TTL: it is
    whatever was left of the access token that bought this one.
    """

    value: str
    expires_in: int
