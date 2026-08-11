"""Health endpoint: must go unhealthy when the embedded worker dies."""

import asyncio
import contextlib
import logging

import pytest
from httpx import AsyncClient

from src.main import _log_embedded_worker_exit, app  # pyright: ignore[reportPrivateUsage]


async def _dead_task(error: BaseException | None = None) -> asyncio.Task[None]:
    async def run() -> None:
        if error is not None:
            raise error

    task = asyncio.create_task(run())
    await asyncio.gather(task, return_exceptions=True)
    return task


async def _wait_forever() -> None:
    await asyncio.Event().wait()


async def test_health_healthy_without_embedded_worker(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


async def test_health_healthy_while_worker_running(client: AsyncClient) -> None:
    task = asyncio.create_task(_wait_forever())
    app.state.embedded_worker_task = task
    try:
        response = await client.get("/health")
    finally:
        del app.state.embedded_worker_task
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


async def test_health_unhealthy_when_worker_task_has_exited(client: AsyncClient) -> None:
    app.state.embedded_worker_task = await _dead_task(RuntimeError("worker died"))
    try:
        response = await client.get("/health")
    finally:
        del app.state.embedded_worker_task

    assert response.status_code == 503
    assert response.json() == {
        "status": "unhealthy",
        "reason": "embedded worker not running",
    }


async def test_worker_crash_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.ERROR)

    _log_embedded_worker_exit(await _dead_task(RuntimeError("boom")))

    crashes = [r for r in caplog.records if "embedded_worker_crashed" in r.getMessage()]
    assert len(crashes) == 1
    assert crashes[0].levelno == logging.ERROR


async def test_worker_cancellation_is_not_logged_as_crash(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR)
    task = asyncio.create_task(_wait_forever())
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)

    _log_embedded_worker_exit(task)

    assert not caplog.records
