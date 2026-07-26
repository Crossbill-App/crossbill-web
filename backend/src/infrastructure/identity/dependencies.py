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


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    use_case: Annotated[
        GetUserByIdUseCase,
        Depends(inject_use_case(container.identity.get_user_by_id_use_case)),
    ],
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
    user_id = verify_access_token(token)
    if user_id is None:
        raise AuthenticationError("Could not validate credentials")

    try:
        return await use_case.get_user(user_id)
    except UserNotFoundError:
        raise AuthenticationError("Could not validate credentials") from None
