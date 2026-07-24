"""Tests for password hashing cost containment."""

import asyncio
import threading
import time

import pytest

from src.config import get_settings
from src.infrastructure.identity.services import password_service


async def test_password_round_trips() -> None:
    hashed = await password_service.hash_password("correct horse battery staple")

    assert await password_service.verify_password("correct horse battery staple", hashed)
    assert not await password_service.verify_password("wrong password", hashed)


async def test_hashing_does_not_block_the_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """A slow hash must not stall unrelated request handling."""
    monkeypatch.setattr(password_service, "_hash_sync", lambda _: (time.sleep(0.1), "hashed")[1])

    ticks = 0

    async def tick_until(task: asyncio.Task[str]) -> None:
        nonlocal ticks
        while not task.done():
            ticks += 1
            await asyncio.sleep(0)

    task = asyncio.create_task(password_service.hash_password("password"))
    await tick_until(task)
    await task

    assert ticks > 10, "event loop was starved while hashing"


async def test_concurrent_hashing_is_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each Argon2 call costs ~64 MiB, so a login flood must not run them all at once."""
    lock = threading.Lock()
    in_flight = 0
    peak = 0

    def slow_hash(_: str) -> str:
        nonlocal in_flight, peak
        with lock:
            in_flight += 1
            peak = max(peak, in_flight)
        time.sleep(0.05)
        with lock:
            in_flight -= 1
        return "hashed"

    monkeypatch.setattr(password_service, "_hash_sync", slow_hash)

    await asyncio.gather(*(password_service.hash_password("password") for _ in range(8)))

    assert peak <= get_settings().PASSWORD_HASH_CONCURRENCY


def _count_verify_calls(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Replace the underlying hash comparison with an always-failing counter."""
    calls = [0]

    def counting_verify(_password: str, _hash: str) -> bool:
        calls[0] += 1
        return False

    monkeypatch.setattr(password_service.password_hash, "verify", counting_verify)
    return calls


async def test_failed_verification_hashes_once_when_no_pepper_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without a pepper the legacy fallback is identical to the first attempt."""
    monkeypatch.setattr(password_service, "PASSWORD_PEPPER", "")
    calls = _count_verify_calls(monkeypatch)

    assert not await password_service.verify_password("password", "hash")
    assert calls[0] == 1


async def test_failed_verification_still_tries_legacy_hash_when_peppered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(password_service, "PASSWORD_PEPPER", "pepper")
    calls = _count_verify_calls(monkeypatch)

    assert not await password_service.verify_password("password", "hash")
    assert calls[0] == 2


async def test_peppered_success_costs_the_same_as_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A short circuit on the peppered hit would leak which hashes are legacy."""
    monkeypatch.setattr(password_service, "PASSWORD_PEPPER", "pepper")
    calls = [0]

    def verify_peppered_only(password: str, _hash: str) -> bool:
        calls[0] += 1
        return password == "passwordpepper"

    monkeypatch.setattr(password_service.password_hash, "verify", verify_peppered_only)

    assert await password_service.verify_password("password", "hash")
    assert calls[0] == 2


async def test_legacy_hash_still_verifies_when_peppered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(password_service, "PASSWORD_PEPPER", "pepper")

    def verify_unpeppered_only(password: str, _hash: str) -> bool:
        return password == "password"

    monkeypatch.setattr(password_service.password_hash, "verify", verify_unpeppered_only)

    assert await password_service.verify_password("password", "hash")
