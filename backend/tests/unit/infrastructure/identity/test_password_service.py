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


@pytest.fixture
def recorded_verifies(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record the passwords handed to the hash comparison, which always fails."""
    seen: list[str] = []

    def recording_verify(password: str, _hash: str) -> bool:
        seen.append(password)
        return False

    monkeypatch.setattr(password_service.password_hash, "verify", recording_verify)
    return seen


@pytest.mark.parametrize("pepper", ["", "pepper"])
async def test_verification_costs_exactly_one_hash(
    monkeypatch: pytest.MonkeyPatch, recorded_verifies: list[str], pepper: str
) -> None:
    """Every login pays one Argon2 verification, peppered or not."""
    monkeypatch.setattr(password_service, "PASSWORD_PEPPER", pepper)

    assert not await password_service.verify_password("password", "hash")
    assert recorded_verifies == ["password" + pepper]


async def test_unparseable_stored_hash_is_a_failed_login() -> None:
    """A hash pwdlib cannot read must not turn a login into a 500."""
    assert not await password_service.verify_password("password", "not-a-hash")
