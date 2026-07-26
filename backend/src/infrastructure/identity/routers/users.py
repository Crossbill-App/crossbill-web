from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from src.application.identity.commands.register_user_use_case import RegisterUserUseCase
from src.application.identity.commands.update_user_use_case import UpdateUserUseCase
from src.core import container
from src.database import DatabaseSession
from src.domain.identity.entities.user import User
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.common.rate_limit import limiter
from src.infrastructure.identity.dependencies import get_current_user
from src.infrastructure.identity.routers.auth import (
    clear_refresh_cookie,
    set_refresh_cookie,
    token_pair_to_response,
)
from src.infrastructure.identity.schemas import (
    UserDetailsResponse,
    UserRegisterRequest,
    UserUpdateRequest,
)
from src.infrastructure.identity.services.token_service import TokenWithRefresh

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/register")
@limiter.limit("5/minute")  # type: ignore[misc]
async def register(
    request: Request,
    response: Response,
    register_data: UserRegisterRequest,
    use_case: RegisterUserUseCase = Depends(
        inject_use_case(container.identity.register_user_use_case)
    ),
) -> TokenWithRefresh:
    """
    Register a new user account.

    Creates a new user with the provided email and password.
    Returns token pair for immediate login after registration.
    """
    _, token_pair = await use_case.register_user(register_data.email, register_data.password)
    set_refresh_cookie(response, token_pair.refresh_token)
    return token_pair_to_response(token_pair)


@router.get("/me")
async def get_me(current_user: Annotated[User, Depends(get_current_user)]) -> UserDetailsResponse:
    """Get the current user's profile information."""
    return UserDetailsResponse(email=current_user.email, id=current_user.id.value)


@router.post("/me")
async def update_me(
    current_user: Annotated[User, Depends(get_current_user)],
    db: DatabaseSession,
    update_data: UserUpdateRequest,
    response: Response,
    use_case: UpdateUserUseCase = Depends(inject_use_case(container.identity.update_user_use_case)),
) -> UserDetailsResponse:
    """
    Update the current user's profile.

    - To change email: provide `email` field
    - To change password: provide both `current_password` and `new_password` fields

    Changing the password signs every session out, this one included, so clients
    should send the user back to the login screen afterwards.
    """
    user = await use_case.update_user(
        user_id=current_user.id.value,
        email=update_data.email,
        current_password=update_data.current_password,
        new_password=update_data.new_password,
    )
    await db.commit()

    if update_data.new_password is not None:
        # The cookie's token was just revoked; drop it rather than leave the
        # client holding one that can only fail.
        clear_refresh_cookie(response)

    return UserDetailsResponse(email=user.email, id=user.id.value)
