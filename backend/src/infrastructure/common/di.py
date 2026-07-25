from collections.abc import Awaitable, Callable
from typing import TypeVar

from dependency_injector.providers import Provider

from src.database import DatabaseSession, bind_db_session

T = TypeVar("T")


def inject_use_case(provider: Provider[T]) -> Callable[[DatabaseSession], Awaitable[T]]:
    """
    Create a FastAPI dependency for a container provider.

    Binds the request-scoped database session for as long as it takes to build
    the use case, which is where the container reads it. Async so it runs in the
    request's own task, whose context no other request can see.
    """

    async def dependency(db: DatabaseSession) -> T:
        with bind_db_session(db):
            return provider()

    return dependency
