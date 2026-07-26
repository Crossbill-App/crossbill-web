"""Authentication routes."""

import logging
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from starlette import status

from src.application.identity.commands.authentication.authenticate_user_use_case import (
    AuthenticateUserUseCase,
)
from src.application.identity.commands.authentication.logout_use_case import LogoutUseCase
from src.application.identity.commands.authentication.refresh_access_token_use_case import (
    RefreshAccessTokenUseCase,
)
from src.application.identity.dtos import TokenPairWithMetadata
from src.config import get_settings
from src.core import container
from src.domain.identity.exceptions import InvalidCredentialsError
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.common.rate_limit import limiter
from src.infrastructure.identity.services.token_service import (
    REFRESH_TOKEN_EXPIRE_DAYS,
    TokenWithRefresh,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


class RefreshTokenRequest(BaseModel):
    """Request body for refresh token (used by plugins)."""

    refresh_token: str | None = None


def token_pair_to_response(token_pair: TokenPairWithMetadata) -> TokenWithRefresh:
    """Convert TokenPairWithMetadata to HTTP response model."""
    return TokenWithRefresh(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        token_type=token_pair.token_type,
        expires_in=token_pair.expires_in,
    )


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Set the refresh token as an httpOnly cookie."""
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        path="/api/v1/auth",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )


def clear_refresh_cookie(response: Response) -> None:
    """Clear the refresh token cookie."""
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        path="/api/v1/auth",
    )


@router.post("/login")
@limiter.limit("5/minute")  # type: ignore[misc]
async def login(
    request: Request,
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    use_case: AuthenticateUserUseCase = Depends(
        inject_use_case(container.identity.authenticate_user_use_case)
    ),
) -> TokenWithRefresh:
    try:
        _, token_pair = await use_case.authenticate(form_data.username, form_data.password)
        set_refresh_cookie(response, token_pair.refresh_token)
        return token_pair_to_response(token_pair)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


@router.post("/refresh")
@limiter.limit("10/minute")  # type: ignore[misc]
async def refresh(
    request: Request,
    response: Response,
    body: RefreshTokenRequest | None = None,
    refresh_token: Annotated[str | None, Cookie()] = None,
    use_case: RefreshAccessTokenUseCase = Depends(
        inject_use_case(container.identity.refresh_access_token_use_case)
    ),
) -> TokenWithRefresh:
    token = refresh_token
    if not token and body and body.refresh_token:
        token = body.refresh_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required",
        )

    try:
        _, token_pair = await use_case.refresh_token(token)
        set_refresh_cookie(response, token_pair.refresh_token)
        return token_pair_to_response(token_pair)
    except InvalidCredentialsError:
        clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from None


@router.post("/logout")
async def logout(
    response: Response,
    refresh_token: Annotated[str | None, Cookie()] = None,
    use_case: LogoutUseCase = Depends(inject_use_case(container.identity.logout_use_case)),
) -> dict[str, str]:
    await use_case.logout(refresh_token)
    clear_refresh_cookie(response)
    return {"message": "Logged out successfully"}
