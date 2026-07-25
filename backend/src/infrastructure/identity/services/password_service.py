"""Password hashing and verification service.

Argon2id is deliberately expensive: the recommended parameters allocate 64 MiB
and burn ~100 ms of CPU per call. Running that inline on the event loop stalls
every other request for the duration, so hashing runs on its own small thread
pool instead. The pool size is the ceiling on how much memory and CPU a burst of
logins can pin down at once, and keeping the pool separate from asyncio's default
executor means bulk file work cannot crowd out a login, or the reverse.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from src.config import get_settings

settings = get_settings()
PASSWORD_PEPPER = settings.PASSWORD_PEPPER

password_hash = PasswordHash.recommended()

# Generate a real hash so timing-attack prevention in authenticate() works correctly.
# A fake string like "abc123" would cause pwdlib to raise UnknownHashError.
DUMMY_HASH = password_hash.hash("dummy_password_for_timing_attack_prevention")

# Threads are created on demand, so an idle pool costs nothing. Unlike an asyncio
# semaphore, the pool is not bound to an event loop, so the same one serves the
# app, the worker and every test case.
_hash_pool = ThreadPoolExecutor(
    max_workers=settings.PASSWORD_HASH_CONCURRENCY, thread_name_prefix="argon2"
)


def _hash_sync(plain_password: str) -> str:
    return password_hash.hash(plain_password + PASSWORD_PEPPER)


def _verify_sync(plain_password: str, hashed_password: str) -> bool:
    try:
        peppered_matches = password_hash.verify(plain_password + PASSWORD_PEPPER, hashed_password)

        if not PASSWORD_PEPPER:
            # With no pepper configured the legacy attempt below is byte-for-byte
            # the one just made; repeating it would only double the cost.
            return peppered_matches

        # Fallback to non-peppered for backward compatibility (DEPRECATED).
        # This allows existing users to login and change their password.
        #
        # Deliberately not short-circuited on peppered_matches: returning early
        # would make a peppered hash cost one verification and a legacy hash two,
        # and that ~30ms gap is measurable from outside. Cost per call is
        # therefore constant, and bounded by the hashing pool in the callers below.
        legacy_matches = password_hash.verify(plain_password, hashed_password)
        return peppered_matches or legacy_matches
    except UnknownHashError:
        return False


async def hash_password(plain_password: str) -> str:
    """Hash a plain password for storage with pepper."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_hash_pool, _hash_sync, plain_password)


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password.

    Tries with pepper first (current standard), then falls back to non-peppered
    for backward compatibility with existing passwords.

    DEPRECATED: Non-peppered password verification will be removed in a future release.
    Users should change their passwords to migrate to peppered hashes.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_hash_pool, _verify_sync, plain_password, hashed_password)


def get_dummy_hash() -> str:
    """Get a dummy hash for timing attack prevention."""
    return DUMMY_HASH
