"""Identity infrastructure layer."""

from src.infrastructure.identity.dependencies import (
    AuthenticatedCaller,
    UserByIdUseCase,
    get_authenticated_caller,
    get_current_user,
    load_authenticated_user,
    oauth2_scheme,
)
from src.infrastructure.identity.repositories.user_repository import UserRepository

__all__ = [
    "AuthenticatedCaller",
    "UserByIdUseCase",
    "UserRepository",
    "get_authenticated_caller",
    "get_current_user",
    "load_authenticated_user",
    "oauth2_scheme",
]
