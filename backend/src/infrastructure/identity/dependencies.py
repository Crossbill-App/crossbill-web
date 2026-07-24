"""FastAPI dependencies for identity and authentication."""

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from src.core import container
from src.database import DatabaseSession, bind_db_session
from src.domain.common.exceptions import AuthenticationError
from src.domain.identity.entities.user import User
from src.domain.identity.exceptions import UserNotFoundError
from src.infrastructure.identity.services.token_service import verify_access_token

if TYPE_CHECKING:
    pass

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], db: DatabaseSession
) -> User:
    """
    Get the current authenticated user from the access token.

    Args:
        token: JWT access token from Authorization header
        db: Database session

    Returns:
        User domain entity

    Raises:
        AuthenticationError: If token is invalid or user not found
    """
    user_id = verify_access_token(token)
    if user_id is None:
        raise AuthenticationError("Could not validate credentials")

    # The binding only has to cover construction — the use case captures the
    # session then — so it is released before the await rather than held across it.
    with bind_db_session(db):
        use_case = container.identity.get_user_by_id_use_case()

    try:
        return await use_case.get_user(user_id)
    except UserNotFoundError:
        raise AuthenticationError("Could not validate credentials") from None
