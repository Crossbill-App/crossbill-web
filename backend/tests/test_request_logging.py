"""Access-log levels: scanner and SPA traffic must not drown out API traffic."""

import logging

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.config import get_settings
from src.main import RequestIdAndLoggingMiddleware

API_PREFIX = get_settings().API_V1_PREFIX
ACCESS_LOG_EVENTS = ("request_started", "request_completed")


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.add_middleware(RequestIdAndLoggingMiddleware)

    @application.get(f"{API_PREFIX}/books")
    async def books() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        return {"status": "ok"}

    @application.get("/{full_path:path}")
    async def spa(full_path: str) -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        if full_path == "boom":
            raise RuntimeError("kaboom")
        return {"status": "spa"}

    return application


async def _access_log_levels(
    app: FastAPI, path: str, caplog: pytest.LogCaptureFixture
) -> dict[str, int]:
    caplog.set_level(logging.DEBUG)
    caplog.clear()
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get(path)
    return {
        event: record.levelno
        for record in caplog.records
        for event in ACCESS_LOG_EVENTS
        if event in record.getMessage()
    }


@pytest.mark.asyncio
async def test_api_requests_are_logged_at_info(
    app: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    levels = await _access_log_levels(app, f"{API_PREFIX}/books", caplog)

    assert levels == {
        "request_started": logging.INFO,
        "request_completed": logging.INFO,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/.env", "/wp-admin/setup-config.php", "/books/42"])
async def test_static_and_spa_requests_are_logged_at_debug(
    app: FastAPI, caplog: pytest.LogCaptureFixture, path: str
) -> None:
    levels = await _access_log_levels(app, path, caplog)

    assert levels == {
        "request_started": logging.DEBUG,
        "request_completed": logging.DEBUG,
    }


@pytest.mark.asyncio
async def test_server_errors_stay_visible_on_quiet_paths(
    app: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    levels = await _access_log_levels(app, "/boom", caplog)

    assert levels["request_completed"] == logging.WARNING
