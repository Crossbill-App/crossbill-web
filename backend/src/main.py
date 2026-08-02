"""Main FastAPI application."""

import asyncio
import contextlib
import os
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.config import configure_logging, get_settings
from src.database import dispose_engine, get_session_factory, initialize_database
from src.domain.common.exceptions import (
    AuthenticationError,
    AuthorizationError,
    BusinessRuleViolationError,
    ConflictError,
    DomainError,
    EntityNotFoundError,
    ValidationError,
)
from src.infrastructure.common.client_ip import client_ip, client_ip_from_scope, proxy_chain
from src.infrastructure.common.openapi import operation_id
from src.infrastructure.common.rate_limit import RateLimitMiddleware, limiter
from src.infrastructure.common.routers import settings as settings_router
from src.infrastructure.identity.repositories.user_repository import UserRepository
from src.infrastructure.identity.routers import auth, users
from src.infrastructure.identity.services.password_service import hash_password
from src.infrastructure.jobs.routers import job_batches
from src.infrastructure.jobs.saq_job_queue_service import SaqJobQueueService
from src.infrastructure.jobs.saq_queue import create_queue
from src.infrastructure.learning.routers import (
    ai_chapter_flashcard_suggestions,
    ai_flashcard_suggestions,
    ai_note_flashcard_suggestions,
    chat_sessions,
    flashcards,
    highlight_flashcards,
    note_flashcards,
)
from src.infrastructure.learning.routers import book_flashcards as learning_books
from src.infrastructure.library.routers import books as library_books
from src.infrastructure.library.routers import covers as library_covers
from src.infrastructure.library.routers import ereader as library_ereader
from src.infrastructure.notes.routers import notes as notes_router
from src.infrastructure.reading.routers import (
    bookmarks,
    chapter_content,
    chapter_digest,
    highlight_labels,
    highlights,
    reading_sessions,
)
from src.infrastructure.reflection.routers import book_reflections as reflection_router
from src.infrastructure.tagging.routers import tags as tagging_tags

settings = get_settings()

# Configure structured logging
configure_logging(settings.ENVIRONMENT)

logger = structlog.get_logger(__name__)

# Directory for frontend static files
STATIC_DIR = (Path(__file__).parent.parent / "static").resolve()


async def _initialize_admin_password() -> None:
    """Initialize admin user password from environment variable if not set."""
    session_factory = get_session_factory(settings)
    async with session_factory() as db:
        # Use repository to find and update admin user
        user_repository = UserRepository(db)
        admin_user = await user_repository.find_by_email(settings.ADMIN_USERNAME)

        if not admin_user:
            logger.warning(
                "admin_user_not_found",
                username=settings.ADMIN_USERNAME,
            )
            return

        if admin_user.has_password():
            logger.info(
                "admin_password_skip",
                reason="password already set",
                username=settings.ADMIN_USERNAME,
            )
            return

        # Hash password and update domain entity
        hashed = await hash_password(settings.ADMIN_PASSWORD)
        admin_user.update_password(hashed)

        # Save via repository
        await user_repository.save(admin_user)
        await db.commit()

        logger.info(
            "admin_password_initialized",
            username=settings.ADMIN_USERNAME,
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager."""
    # Initialize database engine and connection pool once at startup
    initialize_database(settings)

    # Skip database initialization during tests
    if not os.getenv("TESTING"):
        await _initialize_admin_password()

    # Initialize SAQ queue for job enqueueing
    from src.core import container  # noqa: PLC0415

    saq_queue = create_queue(settings.DATABASE_URL)
    await saq_queue.connect()
    queue_service = SaqJobQueueService(saq_queue)
    container.job_queue_service.override(queue_service)

    # Start embedded worker if enabled (runs SAQ in the same process)
    embedded_worker = None
    worker_task: asyncio.Task[None] | None = None
    if settings.EMBEDDED_WORKER:
        from src.worker import create_embedded_worker  # noqa: PLC0415

        embedded_worker = create_embedded_worker(saq_queue, concurrency=settings.WORKER_CONCURRENCY)
        worker_task = asyncio.create_task(embedded_worker.start())
        logger.info("embedded_worker_started", concurrency=settings.WORKER_CONCURRENCY)

    yield

    # Stop embedded worker gracefully.
    # worker.stop() signals the run-loop to exit, which should resolve
    # worker_task naturally.  The cancel() is a defensive fallback in case
    # start() does not exit cleanly (e.g. stuck awaiting a job).
    if embedded_worker is not None and worker_task is not None:
        await embedded_worker.stop()
        worker_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker_task
        logger.info("embedded_worker_stopped")

    await saq_queue.disconnect()
    container.job_queue_service.reset_override()

    # Cleanup on shutdown
    await dispose_engine()


_docs_enabled = settings.ENVIRONMENT != "production"

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url=f"{settings.API_V1_PREFIX}/docs" if _docs_enabled else None,
    redoc_url=f"{settings.API_V1_PREFIX}/redoc" if _docs_enabled else None,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json" if _docs_enabled else None,
    lifespan=lifespan,
    generate_unique_id_function=operation_id,
)

# Wire the shared rate limiter and install our rate-limit middleware so
# `default_limits` apply to every route (not only those with an explicit
# `@limiter.limit(...)` decorator). We use a local fix for slowapi's
# SlowAPIASGIMiddleware, which re-sends http.response.start on every body
# chunk and breaks multi-chunk streamed responses (FileResponse, StaticFiles).
app.state.limiter = limiter
app.add_middleware(RateLimitMiddleware)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Handle rate limit exceeded errors."""
    logger.warning(
        "rate_limit_exceeded",
        path=request.url.path,
        client_host=client_ip(request),
    )
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Please try again later.",
        },
    )


# Pure ASGI middleware (NOT BaseHTTPMiddleware): wrapping the body via
# BaseHTTPMiddleware truncates FileResponse/StaticFiles bodies, which uvicorn
# rejects with "Response content shorter than Content-Length".
class RequestIdAndLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid.uuid4())
        scope.setdefault("state", {})["request_id"] = request_id

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        client_host = client_ip_from_scope(scope)
        method = scope.get("method")
        path = scope.get("path")

        logger.info(
            "request_started",
            method=method,
            path=path,
            client_host=client_host,
        )

        if settings.LOG_PROXY_CHAIN:
            logger.info("proxy_chain", path=path, **proxy_chain(scope, resolved=client_host))

        start_time = time.time()
        status_code = 500

        async def wrapped_send(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(raw=message["headers"])["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, wrapped_send)
        finally:
            duration = time.time() - start_time
            logger.info(
                "request_completed",
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=round(duration * 1000, 2),
            )


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def wrapped_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(raw=message["headers"])
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Permissions-Policy"] = (
                    "camera=(), microphone=(), geolocation=(), payment=()"
                )
                # robots.txt only asks crawlers not to fetch; this keeps URLs
                # that leak out anyway from being indexed.
                headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
                if settings.ENVIRONMENT != "development":
                    headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                    headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
                    headers["Content-Security-Policy"] = (
                        "default-src 'self'; "
                        "script-src 'self'; "
                        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                        "img-src 'self' data: blob:; "
                        "font-src 'self' https://fonts.gstatic.com; "
                        "connect-src 'self'; "
                        "frame-ancestors 'none'; "
                        "base-uri 'self'; "
                        "form-action 'self'"
                    )
            await send(message)

        await self.app(scope, receive, wrapped_send)


app.add_middleware(RequestIdAndLoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# Configure CORS
# Note: When using wildcard origins, credentials must be False
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials="*" not in settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


DOMAIN_ERROR_STATUS_MAP: list[tuple[type[DomainError], int, str]] = [
    (EntityNotFoundError, 404, "not_found"),
    (ValidationError, 400, "bad_request"),
    (ConflictError, 409, "conflict"),
    (AuthenticationError, 401, "authentication_error"),
    (AuthorizationError, 403, "authorization_error"),
    (BusinessRuleViolationError, 400, "bad_request"),
]

SAFE_MESSAGES: dict[int, str] = {
    404: "The requested resource was not found.",
    400: "The request could not be processed.",
    401: "Authentication failed.",
    403: "You do not have permission to perform this action.",
    409: "The resource already exists or conflicts with current state.",
    500: "An unexpected error occurred.",
}


# Exception handlers
@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """Handle all domain exceptions with safe, generic messages."""
    status_code = 500
    error_key = "internal_error"
    for exc_type, code, key in DOMAIN_ERROR_STATUS_MAP:
        if isinstance(exc, exc_type):
            status_code = code
            error_key = key
            break

    if status_code >= 500:  # noqa: PLR2004
        logger.error(
            "domain_error",
            error_type=type(exc).__name__,
            status_code=status_code,
            detail=exc.message,
            exc_info=True,
        )
    else:
        logger.warning(
            "domain_error",
            error_type=type(exc).__name__,
            status_code=status_code,
            detail=exc.message,
        )

    headers: dict[str, str] = {}
    if isinstance(exc, AuthenticationError):
        headers["WWW-Authenticate"] = "Bearer"

    return JSONResponse(
        status_code=status_code,
        content={
            "error": error_key,
            "message": SAFE_MESSAGES[status_code],
        },
        headers=headers or None,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unexpected exceptions. Returns generic 500."""
    logger.error(
        "unhandled_exception",
        exception_type=type(exc).__name__,
        message=str(exc),
        path=request.url.path,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": SAFE_MESSAGES[500],
        },
    )


# Register routers

# Library
app.include_router(library_books.router, prefix=settings.API_V1_PREFIX)
app.include_router(library_ereader.router, prefix=settings.API_V1_PREFIX)
app.include_router(library_covers.router, prefix=settings.API_V1_PREFIX)

# Reading
app.include_router(highlights.router, prefix=settings.API_V1_PREFIX)
app.include_router(tagging_tags.router, prefix=settings.API_V1_PREFIX)
app.include_router(reading_sessions.router, prefix=settings.API_V1_PREFIX)
app.include_router(bookmarks.router, prefix=settings.API_V1_PREFIX)
app.include_router(chapter_digest.router, prefix=settings.API_V1_PREFIX)
app.include_router(chapter_digest.book_digest_router, prefix=settings.API_V1_PREFIX)
app.include_router(chapter_content.router, prefix=settings.API_V1_PREFIX)
app.include_router(highlight_labels.router, prefix=settings.API_V1_PREFIX)

# Learning
app.include_router(learning_books.router, prefix=settings.API_V1_PREFIX)
app.include_router(flashcards.router, prefix=settings.API_V1_PREFIX)
app.include_router(ai_flashcard_suggestions.router, prefix=settings.API_V1_PREFIX)
app.include_router(ai_chapter_flashcard_suggestions.router, prefix=settings.API_V1_PREFIX)
app.include_router(highlight_flashcards.router, prefix=settings.API_V1_PREFIX)
app.include_router(note_flashcards.router, prefix=settings.API_V1_PREFIX)
app.include_router(ai_note_flashcard_suggestions.router, prefix=settings.API_V1_PREFIX)
app.include_router(chat_sessions.router, prefix=settings.API_V1_PREFIX)

# Identity
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(users.router, prefix=settings.API_V1_PREFIX)

# Jobs
app.include_router(job_batches.router, prefix=settings.API_V1_PREFIX)

# Notes
app.include_router(notes_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(reflection_router.router, prefix=settings.API_V1_PREFIX)

# Common
app.include_router(settings_router.router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
@limiter.exempt  # type: ignore[misc]
async def health() -> dict[str, str]:
    """Health check endpoint. Exempt from rate limit so probes never trip it."""
    return {"status": "healthy"}


@app.get(f"{settings.API_V1_PREFIX}/")
async def api_root() -> dict[str, Any]:
    """API root endpoint."""
    response: dict[str, Any] = {
        "message": "crossbill API v1",
        "version": settings.VERSION,
    }
    if _docs_enabled:
        response["docs"] = f"{settings.API_V1_PREFIX}/docs"
    return response


# Mount static files for frontend assets (JS, CSS, etc.)
# Only mount if static directory exists (for development without built frontend)
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="static_assets")

    # Catch-all route for SPA - serves index.html for all other routes
    # This must be last to not interfere with API routes
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str) -> FileResponse:
        """Serve the SPA for all non-API routes."""
        # If the path is a file that exists in static, serve it
        file_path = (STATIC_DIR / full_path).resolve()

        # Validate that the resolved path is within STATIC_DIR to prevent path traversal
        if not file_path.is_relative_to(STATIC_DIR):
            raise HTTPException(status_code=404, detail="Not found")

        if file_path.is_file():
            return FileResponse(file_path)
        # Otherwise serve index.html for client-side routing
        return FileResponse(STATIC_DIR / "index.html")
