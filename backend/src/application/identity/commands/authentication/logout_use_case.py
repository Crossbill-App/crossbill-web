"""Use case for logging out by revoking the refresh token family."""

import structlog

from src.application.identity.protocols.refresh_token_repository import (
    RefreshTokenRepositoryProtocol,
)
from src.application.identity.protocols.token_service import TokenServiceProtocol

logger = structlog.get_logger(__name__)


class LogoutUseCase:
    """Revoke the refresh token family on logout."""

    def __init__(
        self,
        token_service: TokenServiceProtocol,
        refresh_token_repository: RefreshTokenRepositoryProtocol,
    ) -> None:
        self.token_service = token_service
        self.refresh_token_repository = refresh_token_repository

    async def logout(self, refresh_token: str | None) -> None:
        if not refresh_token:
            return

        claims = self.token_service.verify_refresh_token(refresh_token)
        if claims is None:
            return

        existing_token = await self.refresh_token_repository.find_by_jti(claims.jti)
        if existing_token is None:
            return

        await self.refresh_token_repository.revoke_family(existing_token.family_id)

        logger.info(
            "user_logged_out",
            user_id=claims.user_id,
            family_id=existing_token.family_id,
        )
