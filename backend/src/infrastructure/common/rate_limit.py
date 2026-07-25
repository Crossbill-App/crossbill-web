"""Shared rate limiter instance used app-wide.

A single Limiter instance is exposed so that per-route ``@limiter.limit(...)``
decorators (e.g. on auth endpoints) and the global ``default_limits`` share
the same internal state. Using separate Limiter instances would cause the
global default to stack on top of per-route limits instead of being
overridden by them.
"""

from slowapi import Limiter
from slowapi.middleware import _ASGIMiddlewareResponder  # pyright: ignore[reportPrivateUsage]
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.config import get_settings
from src.infrastructure.common.client_ip import client_ip

_settings = get_settings()

# Deliberately not slowapi's get_remote_address: that reads request.client.host,
# which uvicorn rewrites from a client-supplied X-Forwarded-For entry whenever
# proxy headers are trusted. See src/infrastructure/common/client_ip.py.
limiter = Limiter(
    key_func=client_ip,
    default_limits=[_settings.RATE_LIMIT_DEFAULT],
    enabled=_settings.RATE_LIMIT_ENABLED,
    headers_enabled=True,
)


class _FixedResponder(_ASGIMiddlewareResponder):
    """slowapi 0.1.9 re-sends initial_message for every body chunk, which makes
    uvicorn raise on multi-chunk responses (e.g. FileResponse for a JS bundle).
    Send it exactly once and pass through other message types unchanged.
    """

    _initial_sent: bool = False

    async def send_wrapper(self, message: Message) -> None:
        msg_type = message["type"]

        if msg_type == "http.response.start":
            if not self._initial_sent:
                self.initial_message = message
            return

        if msg_type == "http.response.body":
            if not self._initial_sent:
                if self.error_response:
                    self.initial_message["status"] = self.error_response.status_code
                if self.inject_headers:
                    headers = MutableHeaders(raw=self.initial_message["headers"])
                    self.limiter._inject_asgi_headers(  # pyright: ignore[reportPrivateUsage]
                        headers, self.request.state.view_rate_limit
                    )
                await self.send(self.initial_message)
                self._initial_sent = True
            await self.send(message)
            return

        await self.send(message)


class RateLimitMiddleware:
    """ASGI rate-limit middleware that wraps slowapi but fixes its multi-chunk
    initial-message bug.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        await _FixedResponder(self.app)(scope, receive, send)
