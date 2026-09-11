"""FastAPI dependencies for identity and authentication."""

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from src.application.identity.queries.get_user_by_id_use_case import GetUserByIdUseCase
from src.core import container
from src.domain.common.exceptions import AuthenticationError
from src.domain.identity.entities.user import User
from src.domain.identity.exceptions import UserNotFoundError
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.identity.services.token_service import verify_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

_CREDENTIALS_ERROR = "Could not validate credentials"

UserByIdUseCase = Annotated[
    GetUserByIdUseCase,
    Depends(inject_use_case(container.identity.get_user_by_id_use_case)),
]


@dataclass(frozen=True)
class AuthenticatedCaller:
    """A Bearer-authenticated caller, with the expiry of the token that authenticated them."""

    user: User
    access_token_expires_at: datetime


async def load_authenticated_user(use_case: GetUserByIdUseCase, user_id: int) -> User:
    """Load the user a verified credential names.

    A credential that verifies but names nobody is a failed authentication, not
    a missing entity: it was issued for a user since deleted.

    Raises:
        AuthenticationError: If no such user exists.
    """
    try:
        return await use_case.get_user(user_id)
    except UserNotFoundError:
        raise AuthenticationError(_CREDENTIALS_ERROR) from None


async def _authenticated_caller(token: str, use_case: GetUserByIdUseCase) -> AuthenticatedCaller:
    claims = verify_access_token(token)
    if claims is None:
        raise AuthenticationError(_CREDENTIALS_ERROR)
    user = await load_authenticated_user(use_case, claims.user_id)
    return AuthenticatedCaller(user=user, access_token_expires_at=claims.expires_at)


async def get_authenticated_caller(
    token: Annotated[str, Depends(oauth2_scheme)],
    use_case: UserByIdUseCase,
) -> AuthenticatedCaller:
    """Get the current user together with how long their access token has left.

    For routes that mint a credential of their own, whose lifetime has to be
    bounded by the Bearer token's; everywhere else wants ``get_current_user``.

    Raises:
        AuthenticationError: If the token is invalid or names no user.
    """
    return await _authenticated_caller(token, use_case)


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    use_case: UserByIdUseCase,
) -> User:
    """Get the current authenticated user from the access token.

    Raises:
        AuthenticationError: If the token is invalid or names no user.
    """
    return (await _authenticated_caller(token, use_case)).user
