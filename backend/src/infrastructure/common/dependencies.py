"""FastAPI dependencies for the application."""

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from fastapi import HTTPException, status

from src.feature_flags import is_ai_enabled, is_embeddings_enabled

F = TypeVar("F", bound=Callable[..., Any])


def require_ai_enabled(func: F) -> F:
    """
    Decorator that requires AI to be enabled for the endpoint.

    Returns HTTP 410 Gone if AI features are disabled.

    Usage:
        @router.get("/endpoint")
        @require_ai_enabled
        async def my_endpoint():
            ...
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        if not is_ai_enabled():
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="AI features are not enabled on this server",
            )
        return await func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def require_embeddings_enabled(func: F) -> F:
    """
    Decorator that requires semantic-search embeddings to be enabled.

    Returns HTTP 403 Forbidden if no embedding provider is configured. (403
    rather than the 410 Gone ``require_ai_enabled`` uses: 410 means the resource
    existed and was permanently removed, not that it was never configured here.
    Aligning the AI endpoints is a separate change.)

    Works as a decorator only because the embedding client is built lazily -- see
    ``LazyEmbeddingClient``. A decorator body runs after FastAPI has resolved the
    endpoint's parameter dependencies, so a client that checked its settings at
    construction would answer 500 from the dependency graph before this ever ran.

    Usage:
        @router.get("/endpoint")
        @require_embeddings_enabled
        async def my_endpoint():
            ...
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        if not is_embeddings_enabled():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Semantic-search embeddings are not enabled on this server",
            )
        return await func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]
