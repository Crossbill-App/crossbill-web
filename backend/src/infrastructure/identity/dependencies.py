"""FastAPI dependencies for identity and authentication."""

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

# The same scheme, without the 401 it raises for itself when the header is
# missing. It is what lets a route accept a second credential (the web reader's
# publication cookie, #737) instead of stopping at the absent Authorization
# header.
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

CREDENTIALS_ERROR = "Could not validate credentials"

UserByIdUseCase = Annotated[
    GetUserByIdUseCase,
    Depends(inject_use_case(container.identity.get_user_by_id_use_case)),
]


async def load_authenticated_user(use_case: GetUserByIdUseCase, user_id: int) -> User:
    """Load the user a verified credential names.

    A credential that survived verification but names nobody is a failed
    authentication rather than a missing entity: the token was issued for a user
    who has since been deleted.

    Raises:
        AuthenticationError: If no such user exists.
    """
    try:
        return await use_case.get_user(user_id)
    except UserNotFoundError:
        raise AuthenticationError(CREDENTIALS_ERROR) from None


async def _user_for_access_token(token: str, use_case: GetUserByIdUseCase) -> User:
    """Resolve an access token to the user it was issued for.

    Raises:
        AuthenticationError: If the token does not verify, or names no user.
    """
    user_id = verify_access_token(token)
    if user_id is None:
        raise AuthenticationError(CREDENTIALS_ERROR)
    return await load_authenticated_user(use_case, user_id)


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    use_case: UserByIdUseCase,
) -> User:
    """
    Get the current authenticated user from the access token.

    Args:
        token: JWT access token from Authorization header
        use_case: Use case built against the request-scoped database session

    Returns:
        User domain entity

    Raises:
        AuthenticationError: If token is invalid or user not found
    """
    return await _user_for_access_token(token, use_case)


async def get_current_user_optional(
    token: Annotated[str | None, Depends(optional_oauth2_scheme)],
    use_case: UserByIdUseCase,
) -> User | None:
    """Get the current user when the request carries a Bearer token, ``None`` when it does not.

    Only an absent Authorization header is ``None``. A header that is there and
    does not verify still fails the request: a caller presenting a broken Bearer
    token is told so, rather than quietly falling through to whatever other
    credential the route also accepts.

    Raises:
        AuthenticationError: If a token was presented and is invalid, or names
            no user.
    """
    if token is None:
        return None
    return await _user_for_access_token(token, use_case)
