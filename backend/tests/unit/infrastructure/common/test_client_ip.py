"""Tests for originating-client-IP resolution behind reverse proxies."""

import pytest

from src.config import get_settings
from src.infrastructure.common.client_ip import UNKNOWN_CLIENT, client_ip_from_scope


@pytest.fixture
def _one_trusted_hop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "TRUSTED_PROXY_HOPS", 1)


@pytest.fixture
def _no_trusted_hops(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "TRUSTED_PROXY_HOPS", 0)


def _scope(forwarded_for: str | None = None, peer: str | None = "10.0.0.1") -> dict[str, object]:
    headers: list[tuple[bytes, bytes]] = []
    if forwarded_for is not None:
        headers.append((b"x-forwarded-for", forwarded_for.encode()))
    return {
        "type": "http",
        "headers": headers,
        "client": (peer, 12345) if peer else None,
    }


@pytest.mark.usefixtures("_no_trusted_hops")
def test_forwarded_for_is_ignored_when_no_proxy_is_trusted() -> None:
    scope = _scope(forwarded_for="1.2.3.4")

    assert client_ip_from_scope(scope) == "10.0.0.1"


@pytest.mark.usefixtures("_one_trusted_hop")
def test_uses_entry_appended_by_the_trusted_proxy() -> None:
    scope = _scope(forwarded_for="203.0.113.9")

    assert client_ip_from_scope(scope) == "203.0.113.9"


@pytest.mark.usefixtures("_one_trusted_hop")
def test_client_supplied_entries_cannot_displace_the_proxy_appended_one() -> None:
    """The spoofing attempt sits to the left; only the rightmost hop counts."""
    scope = _scope(forwarded_for="1.2.3.4, 5.6.7.8, 203.0.113.9")

    assert client_ip_from_scope(scope) == "203.0.113.9"


@pytest.mark.usefixtures("_one_trusted_hop")
def test_falls_back_to_peer_when_request_bypasses_the_proxy() -> None:
    scope = _scope(forwarded_for=None)

    assert client_ip_from_scope(scope) == "10.0.0.1"


@pytest.mark.usefixtures("_one_trusted_hop")
def test_falls_back_to_peer_when_header_is_blank() -> None:
    scope = _scope(forwarded_for="   ")

    assert client_ip_from_scope(scope) == "10.0.0.1"


@pytest.mark.usefixtures("_one_trusted_hop")
def test_unattributable_requests_share_one_bucket() -> None:
    scope = _scope(forwarded_for=None, peer=None)

    assert client_ip_from_scope(scope) == UNKNOWN_CLIENT


def test_second_hop_is_used_behind_two_proxies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "TRUSTED_PROXY_HOPS", 2)
    scope = _scope(forwarded_for="1.2.3.4, 203.0.113.9, 172.16.0.1")

    assert client_ip_from_scope(scope) == "203.0.113.9"


def test_short_header_is_rejected_rather_than_misindexed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fewer entries than trusted hops means the chain was bypassed."""
    monkeypatch.setattr(get_settings(), "TRUSTED_PROXY_HOPS", 2)
    scope = _scope(forwarded_for="1.2.3.4")

    assert client_ip_from_scope(scope) == "10.0.0.1"
