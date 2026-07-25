"""Resolution of the originating client IP when running behind reverse proxies.

``X-Forwarded-For`` grows left to right: every proxy appends the address of the
peer it accepted the connection from. Only the rightmost ``TRUSTED_PROXY_HOPS``
entries were written by infrastructure we control — everything left of them was
supplied by the client and is forgeable. Picking the leftmost entry (what
uvicorn's ``--forwarded-allow-ips='*'`` does) therefore hands the rate limiter a
key the caller chooses freely.
"""

from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.types import Scope

from src.config import get_settings

UNKNOWN_CLIENT = "unknown"


def _client_from_forwarded_for(header_value: str, hops: int) -> str | None:
    """Return the address the outermost trusted proxy observed, if present.

    Returns ``None`` when the header holds fewer entries than there are trusted
    hops, which means the request did not arrive through the expected proxy
    chain and nothing in the header can be trusted.
    """
    entries = [entry.strip() for entry in header_value.split(",")]
    entries = [entry for entry in entries if entry]

    if len(entries) < hops:
        return None

    return entries[-hops]


def client_ip_from_scope(scope: Scope) -> str:
    """Resolve the originating client IP for an ASGI scope.

    Falls back to the direct peer address, and finally to a shared
    ``UNKNOWN_CLIENT`` bucket so that unattributable requests are rate limited
    together rather than each getting a fresh allowance.
    """
    hops = get_settings().TRUSTED_PROXY_HOPS

    if hops > 0:
        forwarded = Headers(scope=scope).get("x-forwarded-for")
        if forwarded:
            resolved = _client_from_forwarded_for(forwarded, hops)
            if resolved:
                return resolved

    client = scope.get("client")
    peer = client[0] if client else None
    return peer or UNKNOWN_CLIENT


def client_ip(request: Request) -> str:
    """Resolve the originating client IP for a request (slowapi key function)."""
    return client_ip_from_scope(request.scope)
