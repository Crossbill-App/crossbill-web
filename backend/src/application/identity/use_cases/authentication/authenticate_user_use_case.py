"""Use case for authenticating a user with email and password."""

import uuid

import structlog

from src.application.identity.dtos import TokenPairWithMetadata
from src.application.identity.protocols.password_service import PasswordServiceProtocol
from src.application.identity.protocols.refresh_token_repository import (
    RefreshTokenRepositoryProtocol,
)
from src.application.identity.protocols.token_service import TokenServiceProtocol
from src.application.identity.protocols.user_repository import UserRepositoryProtocol
from src.domain.identity.entities.refresh_token import RefreshToken
from src.domain.identity.entities.user import User
from src.domain.identity.exceptions import InvalidCredentialsError

logger = structlog.get_logger(__name__)


class AuthenticateUserUseCase:
    """Use case for authenticating a user with email and password."""

    def __init__(
        self,
        user_repository: UserRepositoryProtocol,
        password_service: PasswordServiceProtocol,
        token_service: TokenServiceProtocol,
        refresh_token_repository: RefreshTokenRepositoryProtocol,
    ) -> None:
        self.user_repository = user_repository
        self.password_service = password_service
        self.token_service = token_service
        self.refresh_token_repository = refresh_token_repository

    async def authenticate(self, email: str, password: str) -> tuple[User, TokenPairWithMetadata]:
        user = await self.user_repository.find_by_email(email)

        if not user:
            await self.password_service.verify_password(
                password, self.password_service.get_dummy_hash()
            )
            raise InvalidCredentialsError

        if not user.hashed_password or not await self.password_service.verify_password(
            password, user.hashed_password
        ):
            raise InvalidCredentialsError

        family_id = str(uuid.uuid4())
        token_pair = self.token_service.create_token_pair(user.id.value, family_id)

        refresh_token_entity = RefreshToken.create(
            jti=token_pair.jti,
            user_id=user.id,
            family_id=token_pair.family_id,
            expires_at=token_pair.refresh_token_expires_at,
        )
        await self.refresh_token_repository.save(refresh_token_entity)

        logger.info("user_authenticated", user_id=user.id.value, email=email)

        return user, token_pair
