"""Resolution of the originating client IP when running behind reverse proxies.

The only fact about a request the caller cannot influence is the TCP peer
address, so that is what decides whether any header may be believed: when the
peer is one of ``TRUSTED_PROXY_CIDRS``, the request demonstrably arrived through
a proxy we control and the client it names in ``X-Real-IP`` is that proxy's
statement rather than the caller's.

``X-Forwarded-For`` cannot stand in for that, because it does not mean the same
thing everywhere. Proxies that *append* add their peer to whatever the caller
sent, leaving only the rightmost ``TRUSTED_PROXY_HOPS`` entries believable.
Railway instead *rewrites* the header, so a request arriving through Cloudflare
reaches the app with the browser's address absent entirely and no hop count can
find it. ``.env.example`` documents how to configure each.
"""

from collections.abc import Sequence
from ipaddress import IPv4Network, IPv6Network, ip_address

from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.types import Scope

from src.config import get_settings

UNKNOWN_CLIENT = "unknown"

# Header a trusted proxy reports the originating client in. Railway and nginx
# both use this one, and Railway substitutes Cf-Connecting-IP into it when the
# request came from trusted Cloudflare infrastructure, so fronting the app with
# Cloudflare needs no separate handling here.
CLIENT_HEADER = "x-real-ip"


def _within(address: str, networks: Sequence[IPv4Network | IPv6Network]) -> bool:
    try:
        parsed = ip_address(address)
    except ValueError:
        return False
    return any(parsed in network for network in networks)


def _address_or_none(value: str | None) -> str | None:
    """Return ``value`` only when it is a usable IP address.

    Anything else would become a rate-limit key of the caller's choosing, so a
    malformed header is treated as absent rather than passed through.
    """
    if value is None:
        return None
    candidate = value.strip()
    try:
        ip_address(candidate)
    except ValueError:
        return None
    return candidate


def _sole_header(headers: Headers, name: str) -> str | None:
    """Return a header's value only when it appears exactly once.

    Reading just the first of several occurrences is what lets a caller shadow a
    value the proxy set, so repetition is treated as untrustworthy rather than
    resolved to one of the candidates.
    """
    values = headers.getlist(name)
    if len(values) != 1:
        return None
    return values[0]


def _client_from_forwarded_for(header_value: str, hops: int) -> str | None:
    """Return the address the outermost appending proxy observed, if present.

    Returns ``None`` when the header holds fewer entries than there are trusted
    hops, which means the request did not arrive through the expected proxy
    chain and nothing in the header can be trusted.
    """
    entries = [entry.strip() for entry in header_value.split(",")]
    entries = [entry for entry in entries if entry]

    if len(entries) < hops:
        return None
    return entries[-hops]


def _peer(scope: Scope) -> str | None:
    client = scope.get("client")
    return client[0] if client else None


def client_ip_from_scope(scope: Scope) -> str:
    """Resolve the originating client IP for an ASGI scope.

    Falls back to the direct peer address, and finally to a shared
    ``UNKNOWN_CLIENT`` bucket so that unattributable requests are rate limited
    together rather than each getting a fresh allowance.
    """
    settings = get_settings()
    peer = _peer(scope)

    if peer and _within(peer, settings.TRUSTED_PROXY_CIDRS):
        reported = _address_or_none(_sole_header(Headers(scope=scope), CLIENT_HEADER))
        if reported:
            return reported

    if settings.TRUSTED_PROXY_HOPS > 0:
        forwarded = _sole_header(Headers(scope=scope), "x-forwarded-for")
        if forwarded:
            resolved = _client_from_forwarded_for(forwarded, settings.TRUSTED_PROXY_HOPS)
            if resolved:
                return resolved

    return peer or UNKNOWN_CLIENT


def client_ip(request: Request) -> str:
    """Resolve the originating client IP for a request (slowapi key function)."""
    return client_ip_from_scope(request.scope)
