"""Tests for originating-client-IP resolution behind reverse proxies."""

from ipaddress import ip_network

import pytest

from src.config import get_settings
from src.infrastructure.common.client_ip import UNKNOWN_CLIENT, client_ip_from_scope

# The chain observed in production: Railway's internal proxy is the peer, its
# Oslo PoP and the Cloudflare egress in front of it fill X-Forwarded-For, and the
# browser appears only in X-Real-IP.
RAILWAY_PEER = "100.64.0.6"
CLOUDFLARE_EGRESS = "104.23.217.156"
RAILWAY_POP = "79.127.151.146"
BROWSER = "91.157.105.204"
RAILWAY_CHAIN = f"{CLOUDFLARE_EGRESS}, {RAILWAY_POP}"


def _set_hops(monkeypatch: pytest.MonkeyPatch, hops: int) -> None:
    monkeypatch.setattr(get_settings(), "TRUSTED_PROXY_HOPS", hops)


def _trust_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "TRUSTED_PROXY_CIDRS", [ip_network("100.64.0.0/10")])


def _scope(
    forwarded_for: str | None = None,
    real_ip: str | None = None,
    peer: str | None = "10.0.0.1",
    headers: list[tuple[bytes, bytes]] | None = None,
) -> dict[str, object]:
    """Build an ASGI scope. Pass `headers` to control repetition and ordering."""
    if headers is None:
        headers = []
        if forwarded_for is not None:
            headers.append((b"x-forwarded-for", forwarded_for.encode()))
        if real_ip is not None:
            headers.append((b"x-real-ip", real_ip.encode()))
    return {
        "type": "http",
        "headers": headers,
        "client": (peer, 12345) if peer else None,
    }


def test_forwarded_for_is_ignored_when_no_proxy_is_trusted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_hops(monkeypatch, 0)
    scope = _scope(forwarded_for="1.2.3.4")

    assert client_ip_from_scope(scope) == "10.0.0.1"


def test_uses_entry_appended_by_the_trusted_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_hops(monkeypatch, 1)
    scope = _scope(forwarded_for="203.0.113.9")

    assert client_ip_from_scope(scope) == "203.0.113.9"


def test_client_supplied_entries_cannot_displace_the_proxy_appended_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The spoofing attempt sits to the left; only the rightmost hop counts."""
    _set_hops(monkeypatch, 1)
    scope = _scope(forwarded_for="1.2.3.4, 5.6.7.8, 203.0.113.9")

    assert client_ip_from_scope(scope) == "203.0.113.9"


def test_falls_back_to_peer_when_request_bypasses_the_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_hops(monkeypatch, 1)
    scope = _scope(forwarded_for=None)

    assert client_ip_from_scope(scope) == "10.0.0.1"


def test_falls_back_to_peer_when_header_is_blank(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_hops(monkeypatch, 1)
    scope = _scope(forwarded_for="   ")

    assert client_ip_from_scope(scope) == "10.0.0.1"


def test_unattributable_requests_share_one_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_hops(monkeypatch, 1)
    scope = _scope(forwarded_for=None, peer=None)

    assert client_ip_from_scope(scope) == UNKNOWN_CLIENT


def test_second_hop_is_used_behind_two_proxies(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_hops(monkeypatch, 2)
    scope = _scope(forwarded_for="1.2.3.4, 203.0.113.9, 172.16.0.1")

    assert client_ip_from_scope(scope) == "203.0.113.9"


def test_short_header_is_rejected_rather_than_misindexed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fewer entries than trusted hops means the chain was bypassed."""
    _set_hops(monkeypatch, 2)
    scope = _scope(forwarded_for="1.2.3.4")

    assert client_ip_from_scope(scope) == "10.0.0.1"


@pytest.mark.parametrize("hops", [0, 1])
def test_trusted_proxy_reports_the_client_it_observed(
    monkeypatch: pytest.MonkeyPatch, hops: int
) -> None:
    """The production chain: the client is only in X-Real-IP, not in the chain.

    Parametrized over the hop count because a rewriting proxy leaves nothing
    usable in X-Forwarded-For, so the count must not win when both are set.
    """
    _set_hops(monkeypatch, hops)
    _trust_proxy(monkeypatch)
    scope = _scope(forwarded_for=RAILWAY_CHAIN, real_ip=BROWSER, peer=RAILWAY_PEER)

    assert client_ip_from_scope(scope) == BROWSER


def test_rotating_a_forged_client_header_cannot_mint_buckets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anyone reaching the app off-proxy can set X-Real-IP to whatever they like.

    One caller must still get one bucket, which is the whole point of the
    exercise — so the peer is what counts, not what they claim.
    """
    _set_hops(monkeypatch, 0)
    _trust_proxy(monkeypatch)

    keys = {
        client_ip_from_scope(
            _scope(forwarded_for=RAILWAY_CHAIN, real_ip=forged, peer="203.0.113.99")
        )
        for forged in ("1.2.3.4", "5.6.7.8", "9.10.11.12")
    }

    assert keys == {"203.0.113.99"}


def test_repeated_client_header_is_not_believed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A second X-Real-IP line must not shadow the one the proxy set."""
    _set_hops(monkeypatch, 0)
    _trust_proxy(monkeypatch)
    scope = _scope(
        peer=RAILWAY_PEER,
        headers=[
            (b"x-real-ip", b"203.0.113.99"),
            (b"x-real-ip", BROWSER.encode()),
        ],
    )

    assert client_ip_from_scope(scope) == RAILWAY_PEER


def test_unparseable_client_header_falls_back_to_the_peer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_hops(monkeypatch, 0)
    _trust_proxy(monkeypatch)
    scope = _scope(forwarded_for=RAILWAY_CHAIN, real_ip="not-an-ip", peer=RAILWAY_PEER)

    assert client_ip_from_scope(scope) == RAILWAY_PEER


def test_missing_client_header_falls_back_to_the_peer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Coarse but unforgeable: everyone behind that proxy shares a bucket."""
    _set_hops(monkeypatch, 0)
    _trust_proxy(monkeypatch)
    scope = _scope(forwarded_for=RAILWAY_CHAIN, peer=RAILWAY_PEER)

    assert client_ip_from_scope(scope) == RAILWAY_PEER


def test_trusted_proxy_falls_back_to_the_hop_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """An appending proxy that sets no client header still has a usable chain."""
    _set_hops(monkeypatch, 1)
    _trust_proxy(monkeypatch)
    scope = _scope(forwarded_for=f"1.2.3.4, {BROWSER}", peer=RAILWAY_PEER)

    assert client_ip_from_scope(scope) == BROWSER


def test_trusted_proxy_resolves_an_ipv6_client(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_hops(monkeypatch, 0)
    _trust_proxy(monkeypatch)
    scope = _scope(real_ip="2001:14ba:a086:1900::1", peer=RAILWAY_PEER)

    assert client_ip_from_scope(scope) == "2001:14ba:a086:1900::1"
