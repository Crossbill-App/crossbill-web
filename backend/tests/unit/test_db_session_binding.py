"""Tests that the DI container resolves a per-context database session."""

import asyncio
from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core import container
from src.database import bind_db_session, current_db_session


def _fake_session() -> AsyncSession:
    return MagicMock(spec=AsyncSession)


def test_resolving_without_a_binding_is_an_error() -> None:
    with pytest.raises(RuntimeError, match="No database session is bound"):
        current_db_session()


def test_binding_is_released_after_the_block() -> None:
    with bind_db_session(_fake_session()):
        pass

    with pytest.raises(RuntimeError):
        current_db_session()


def test_nested_bindings_restore_the_outer_session() -> None:
    outer = _fake_session()
    inner = _fake_session()

    with bind_db_session(outer):
        with bind_db_session(inner):
            assert current_db_session() is inner
        assert current_db_session() is outer


def test_repositories_are_built_against_the_bound_session() -> None:
    session = _fake_session()

    with bind_db_session(session):
        repository = container.shared.user_repository()

    assert repository.db is session


async def test_concurrent_tasks_do_not_share_a_session() -> None:
    """Two requests in flight at once must each resolve their own session."""

    async def resolve(session: AsyncSession, delay: float) -> AsyncSession:
        with bind_db_session(session):
            # Yield control so the sibling task binds while this one is suspended.
            await asyncio.sleep(delay)
            repository = container.shared.user_repository()
        return repository.db

    first = _fake_session()
    second = _fake_session()

    resolved_first, resolved_second = await asyncio.gather(
        resolve(first, 0.02), resolve(second, 0.0)
    )

    assert resolved_first is first
    assert resolved_second is second


async def test_a_finished_task_does_not_unbind_a_running_one() -> None:
    """A sibling completing mid-flight must not strip this task's binding."""

    async def short_lived() -> None:
        with bind_db_session(_fake_session()):
            await asyncio.sleep(0)

    session = _fake_session()

    with bind_db_session(session):
        await asyncio.gather(short_lived(), short_lived())
        assert current_db_session() is session
