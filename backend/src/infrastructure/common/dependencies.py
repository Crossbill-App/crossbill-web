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


def require_embeddings_enabled() -> None:
    """
    FastAPI dependency requiring semantic-search embeddings to be enabled.

    Raises HTTP 403 Forbidden if no embedding provider is configured.

    A dependency rather than a decorator (unlike ``require_ai_enabled``) because
    it must run *before* the endpoint's own parameter dependencies: the search
    endpoint injects a use case whose construction builds the embedding client,
    and that raises when no provider is configured. FastAPI solves route-level
    dependencies ahead of parameter dependencies, so the gate answers 403 rather
    than letting the client error surface as a 500.

    Usage:
        @router.post("/endpoint", dependencies=[Depends(require_embeddings_enabled)])
        async def my_endpoint():
            ...
    """
    if not is_embeddings_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Semantic-search embeddings are not enabled on this server",
        )
