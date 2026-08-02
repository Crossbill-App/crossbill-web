"""Regression tests: middleware must not break streamed FileResponse bodies.

Two bugs were observed in production:
1. Starlette's BaseHTTPMiddleware re-streamed FileResponse bodies through a
   memory pipe, causing them to be truncated below the declared Content-Length.
2. slowapi 0.1.9's SlowAPIASGIMiddleware re-sends http.response.start on every
   body chunk, which uvicorn rejects on multi-chunk responses.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from httpx import ASGITransport, AsyncClient
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.infrastructure.common.rate_limit import RateLimitMiddleware
from src.main import RequestIdAndLoggingMiddleware, SecurityHeadersMiddleware


def _build_app(static_dir: Path, *, with_rate_limit: bool = False) -> FastAPI:
    app = FastAPI()
    if with_rate_limit:
        # Enabled limiter with headers — exercises slowapi's send_wrapper path
        # that mishandled multi-chunk responses.
        app.state.limiter = Limiter(
            key_func=get_remote_address,
            default_limits=["1000/minute"],
            enabled=True,
            headers_enabled=True,
        )
        app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestIdAndLoggingMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.mount("/assets", StaticFiles(directory=str(static_dir)), name="assets")

    @app.get("/file")
    async def serve_file() -> FileResponse:  # pyright: ignore[reportUnusedFunction]
        return FileResponse(static_dir / "payload.bin")

    return app


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    # 256 KiB — guarantees multiple 64 KiB chunks in FileResponse.
    payload = b"x" * (256 * 1024)
    (tmp_path / "payload.bin").write_bytes(payload)
    return tmp_path


EXPECTED_SIZE = 256 * 1024


@pytest.mark.asyncio
async def test_file_response_body_not_truncated(static_dir: Path) -> None:
    app = _build_app(static_dir)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/file")

    assert response.status_code == 200
    assert response.headers["content-length"] == str(EXPECTED_SIZE)
    assert len(response.content) == EXPECTED_SIZE
    assert response.content == b"x" * EXPECTED_SIZE


@pytest.mark.asyncio
async def test_staticfiles_body_not_truncated(static_dir: Path) -> None:
    app = _build_app(static_dir)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/assets/payload.bin")

    assert response.status_code == 200
    assert response.headers["content-length"] == str(EXPECTED_SIZE)
    assert len(response.content) == EXPECTED_SIZE


@pytest.mark.asyncio
async def test_request_id_and_security_headers_present(static_dir: Path) -> None:
    app = _build_app(static_dir)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/file")

    assert response.headers.get("x-request-id")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-robots-tag"] == "noindex, nofollow, noarchive"


@pytest.mark.asyncio
async def test_multi_chunk_response_through_rate_limiter(static_dir: Path) -> None:
    """slowapi 0.1.9's send_wrapper would re-send http.response.start for every
    body chunk. With multiple chunks this corrupts the response; uvicorn rejects
    it. The fix sends initial_message once.
    """
    app = _build_app(static_dir, with_rate_limit=True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/file")

    assert response.status_code == 200
    assert len(response.content) == EXPECTED_SIZE
    # Rate limit headers injected once on the (single) http.response.start.
    assert response.headers.get("x-ratelimit-limit")
