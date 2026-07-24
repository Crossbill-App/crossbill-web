from collections.abc import Callable
from typing import TypeVar

from dependency_injector.providers import Provider

from src.database import DatabaseSession, bind_db_session

T = TypeVar("T")


def inject_use_case(provider: Provider[T]) -> Callable[[DatabaseSession], T]:
    """
    Create a FastAPI dependency for a container provider.

    Binds the request-scoped database session for as long as it takes to build
    the use case, which is where the container reads it. The binding is
    context-local, so concurrent requests cannot observe each other's session.
    """

    def dependency(db: DatabaseSession) -> T:
        with bind_db_session(db):
            return provider()

    return dependency
