"""Use case for refreshing access token with token rotation."""

from datetime import timedelta

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
        rotation_grace_seconds: int,
    ) -> None:
        self.user_repository = user_repository
        self.token_service = token_service
        self.refresh_token_repository = refresh_token_repository
        self.rotation_grace = timedelta(seconds=rotation_grace_seconds)

    async def refresh_token(self, refresh_token: str) -> tuple[User, TokenPairWithMetadata]:
        claims = self.token_service.verify_refresh_token(refresh_token)
        if claims is None:
            raise InvalidCredentialsError

        presented = await self.refresh_token_repository.find_by_jti(claims.jti)
        if presented is None:
            raise InvalidCredentialsError

        if presented.is_revoked:
            return await self._answer_spent_token(presented)

        user = await self._require_user(UserId(claims.user_id))
        return user, await self._rotate(user, presented)

    async def _rotate(self, user: User, presented: RefreshToken) -> TokenPairWithMetadata:
        token_pair = self.token_service.create_token_pair(user.id.value, presented.family_id)
        successor = RefreshToken.create(
            jti=token_pair.jti,
            user_id=user.id,
            family_id=presented.family_id,
            expires_at=token_pair.refresh_token_expires_at,
        )
        await self.refresh_token_repository.rotate(presented, successor)
        await self.refresh_token_repository.delete_expired_for_user(user.id)

        logger.info("access_token_refreshed", user_id=user.id.value)
        return token_pair

    async def _answer_spent_token(
        self, presented: RefreshToken
    ) -> tuple[User, TokenPairWithMetadata]:
        """Decide whether a revoked token is a retry to satisfy or a replay to punish."""
        successor = await self._successor_still_usable(presented)
        if successor is None:
            await self.refresh_token_repository.revoke_family(presented.family_id)
            logger.warning(
                "refresh_token_replay_detected",
                jti=presented.jti,
                family_id=presented.family_id,
            )
            raise InvalidCredentialsError

        user = await self._require_user(presented.user_id)
        logger.info(
            "refresh_token_rotation_retried",
            jti=presented.jti,
            successor_jti=successor.jti,
            user_id=user.id.value,
        )
        return user, self.token_service.reissue_token_pair(
            user_id=user.id.value,
            family_id=successor.family_id,
            jti=successor.jti,
            refresh_token_expires_at=successor.expires_at,
        )

    async def _successor_still_usable(self, presented: RefreshToken) -> RefreshToken | None:
        """The replacement to hand back, or None if this reuse is real replay.

        The successor has to be live as well as recent: once it has itself been
        spent, a client presenting its predecessor is a generation behind, which
        no lost response explains.
        """
        successor_jti = presented.successor_within(self.rotation_grace)
        if successor_jti is None:
            return None

        successor = await self.refresh_token_repository.find_by_jti(successor_jti)
        if successor is None or successor.is_revoked or successor.is_expired:
            return None
        return successor

    async def _require_user(self, user_id: UserId) -> User:
        user = await self.user_repository.find_by_id(user_id)
        if user is None:
            raise InvalidCredentialsError
        return user
