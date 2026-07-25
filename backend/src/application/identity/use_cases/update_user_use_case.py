"""Use case for user profile management."""

import structlog

from src.application.identity.protocols.password_service import PasswordServiceProtocol
from src.application.identity.protocols.refresh_token_repository import (
    RefreshTokenRepositoryProtocol,
)
from src.application.identity.protocols.user_repository import UserRepositoryProtocol
from src.domain.common.value_objects.ids import UserId
from src.domain.identity.entities.user import User
from src.domain.identity.exceptions import PasswordVerificationError, UserNotFoundError

logger = structlog.get_logger(__name__)


class UpdateUserUseCase:
    """Use case for user profile operations."""

    def __init__(
        self,
        user_repository: UserRepositoryProtocol,
        password_service: PasswordServiceProtocol,
        refresh_token_repository: RefreshTokenRepositoryProtocol,
    ) -> None:
        """Initialize use case with dependencies."""
        self.user_repository = user_repository
        self.password_service = password_service
        self.refresh_token_repository = refresh_token_repository

    async def update_user(
        self,
        user_id: int,
        email: str | None = None,
        current_password: str | None = None,
        new_password: str | None = None,
    ) -> User:
        """
        Update the user's profile.

        Args:
            user_id: ID of the user to update
            email: New email address (optional)
            current_password: Current password for verification (required if changing password)
            new_password: New password (optional). Changing it signs every session
                out, including the caller's own.

        Returns:
            Updated user entity

        Raises:
            UserNotFoundError: If user is not found
            PasswordVerificationError: If current_password is incorrect
            ValidationError: If email is invalid or current_password not provided when required
        """
        # Load user
        user = await self.user_repository.find_by_id(UserId(user_id))
        if not user:
            raise UserNotFoundError(user_id)

        if email is not None:
            user.update_email(email)

        if new_password is not None:
            if current_password is None:
                raise PasswordVerificationError

            if not user.hashed_password or not await self.password_service.verify_password(
                current_password, user.hashed_password
            ):
                raise PasswordVerificationError

            hashed_password = await self.password_service.hash_password(new_password)
            user.update_password(hashed_password)

        user = await self.user_repository.save(user)

        if new_password is not None:
            # Changing a password is how someone responds to a suspected
            # compromise, so it has to evict sessions a thief may be holding.
            # Refresh tokens live for 30 days and would otherwise outlive it.
            #
            # Every session goes, the caller's included. Sparing the current one
            # would mean identifying it from its refresh cookie, and that cookie
            # is scoped to /api/v1/auth so it never reaches this endpoint.
            await self.refresh_token_repository.revoke_all_for_user(user.id)
            logger.info("sessions_revoked_after_password_change", user_id=user_id)

        logger.info("user_profile_updated", user_id=user_id)

        return user
