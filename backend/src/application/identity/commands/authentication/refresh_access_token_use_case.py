"""Use case for refreshing access token with token rotation."""

import structlog

from src.application.identity.dtos import TokenPairWithMetadata
from src.application.identity.protocols.refresh_token_repository import (
    RefreshTokenRepositoryProtocol,
)
from src.application.identity.protocols.token_service import TokenServiceProtocol
from src.application.identity.protocols.user_repository import UserRepositoryProtocol
from src.domain.common.value_objects.ids import UserId
from src.domain.identity.entities.refresh_token import RefreshToken
from src.domain.identity.entities.user import User
from src.domain.identity.exceptions import InvalidCredentialsError

logger = structlog.get_logger(__name__)


class RefreshAccessTokenUseCase:
    """Use case for refreshing access token with token rotation."""

    def __init__(
        self,
        user_repository: UserRepositoryProtocol,
        token_service: TokenServiceProtocol,
        refresh_token_repository: RefreshTokenRepositoryProtocol,
    ) -> None:
        self.user_repository = user_repository
        self.token_service = token_service
        self.refresh_token_repository = refresh_token_repository

    async def refresh_token(self, refresh_token: str) -> tuple[User, TokenPairWithMetadata]:
        # 1. Verify JWT and extract claims
        claims = self.token_service.verify_refresh_token(refresh_token)
        if claims is None:
            raise InvalidCredentialsError

        # 2. Look up token in DB by jti
        existing_token = await self.refresh_token_repository.find_by_jti(claims.jti)
        if existing_token is None:
            raise InvalidCredentialsError

        # 3. Replay detection: if token is revoked, revoke entire family
        if existing_token.is_revoked:
            await self.refresh_token_repository.revoke_family(existing_token.family_id)
            logger.warning(
                "refresh_token_replay_detected",
                jti=claims.jti,
                family_id=existing_token.family_id,
            )
            raise InvalidCredentialsError

        # 4. Verify user still exists
        user = await self.user_repository.find_by_id(UserId(claims.user_id))
        if not user:
            raise InvalidCredentialsError

        # 5. Revoke current token
        await self.refresh_token_repository.revoke(existing_token)

        # 6. Create new token pair in same family
        token_pair = self.token_service.create_token_pair(user.id.value, existing_token.family_id)

        # 7. Persist new refresh token
        new_token = RefreshToken.create(
            jti=token_pair.jti,
            user_id=user.id,
            family_id=existing_token.family_id,
            expires_at=token_pair.refresh_token_expires_at,
        )
        await self.refresh_token_repository.save(new_token)

        # 8. Lazy cleanup
        await self.refresh_token_repository.delete_expired_for_user(user.id)

        logger.info("access_token_refreshed", user_id=user.id.value)

        return user, token_pair
