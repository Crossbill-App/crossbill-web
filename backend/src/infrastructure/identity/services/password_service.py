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
        return password_hash.verify(plain_password + PASSWORD_PEPPER, hashed_password)
    except UnknownHashError:
        # A stored hash we cannot parse is a failed login, not a 500.
        return False


async def hash_password(plain_password: str) -> str:
    """Hash a plain password for storage with pepper."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_hash_pool, _hash_sync, plain_password)


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a peppered hash.

    Exactly one verification runs, so the cost is the same whether the password
    matches or not.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_hash_pool, _verify_sync, plain_password, hashed_password)


def get_dummy_hash() -> str:
    """Get a dummy hash for timing attack prevention."""
    return DUMMY_HASH
