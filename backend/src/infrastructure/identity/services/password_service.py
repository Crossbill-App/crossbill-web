"""Password hashing and verification service.

Argon2id is deliberately expensive: the recommended parameters allocate 64 MiB
and burn tens of milliseconds per call. Running that inline on the event loop
stalls every other request for the duration, so an unauthenticated caller could
wedge the whole app with a trickle of bad logins. Hashing therefore happens on a
worker thread, and a semaphore caps how many run at once so the memory cost
stays bounded no matter how many requests arrive together.
"""

import asyncio
from weakref import WeakKeyDictionary

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from src.config import get_settings

settings = get_settings()
PASSWORD_PEPPER = settings.PASSWORD_PEPPER

password_hash = PasswordHash.recommended()

# Generate a real hash so timing-attack prevention in authenticate() works correctly.
# A fake string like "abc123" would cause pwdlib to raise UnknownHashError.
DUMMY_HASH = password_hash.hash("dummy_password_for_timing_attack_prevention")

# Keyed by event loop: asyncio primitives bind to the first loop that uses them,
# and the test suite runs each case on a fresh loop.
_concurrency_guards: WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore] = (
    WeakKeyDictionary()
)


def _concurrency_guard() -> asyncio.Semaphore:
    """Get the hashing semaphore for the running event loop."""
    loop = asyncio.get_running_loop()
    guard = _concurrency_guards.get(loop)
    if guard is None:
        guard = asyncio.Semaphore(settings.PASSWORD_HASH_CONCURRENCY)
        _concurrency_guards[loop] = guard
    return guard


def _hash_sync(plain_password: str) -> str:
    return password_hash.hash(plain_password + PASSWORD_PEPPER)


def _verify_sync(plain_password: str, hashed_password: str) -> bool:
    try:
        if password_hash.verify(plain_password + PASSWORD_PEPPER, hashed_password):
            return True

        if not PASSWORD_PEPPER:
            # With no pepper configured the legacy attempt below is byte-for-byte
            # the one we just made; repeating it would only double the cost of
            # every failed login.
            return False

        # Fallback to non-peppered for backward compatibility (DEPRECATED).
        # This allows existing users to login and change their password.
        return password_hash.verify(plain_password, hashed_password)
    except UnknownHashError:
        return False


async def hash_password(plain_password: str) -> str:
    """Hash a plain password for storage with pepper."""
    async with _concurrency_guard():
        return await asyncio.to_thread(_hash_sync, plain_password)


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password.

    Tries with pepper first (current standard), then falls back to non-peppered
    for backward compatibility with existing passwords.

    DEPRECATED: Non-peppered password verification will be removed in a future release.
    Users should change their passwords to migrate to peppered hashes.
    """
    async with _concurrency_guard():
        return await asyncio.to_thread(_verify_sync, plain_password, hashed_password)


def get_dummy_hash() -> str:
    """Get a dummy hash for timing attack prevention."""
    return DUMMY_HASH
