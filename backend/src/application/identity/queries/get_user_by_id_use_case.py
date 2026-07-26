"""Use case for getting a user by ID (used internally by dependency injection)."""

import structlog

from src.application.identity.protocols.user_repository import UserRepositoryProtocol
from src.domain.common.value_objects.ids import UserId
from src.domain.identity.entities.user import User
from src.domain.identity.exceptions import UserNotFoundError

logger = structlog.get_logger(__name__)


class GetUserByIdUseCase:
    """Use case for getting a user by ID (used internally by dependency injection)."""

    def __init__(
        self,
        user_repository: UserRepositoryProtocol,
    ) -> None:
        """Initialize use case with dependencies."""
        self.user_repository = user_repository

    async def get_user(self, user_id: int) -> User:
        """
        Get a user by ID (used internally by dependency injection).

        Args:
            user_id: User's ID

        Returns:
            User entity

        Raises:
            UserNotFoundError: If user is not found
        """
        user = await self.user_repository.find_by_id(UserId(user_id))
        if not user:
            raise UserNotFoundError(user_id)
        return user
