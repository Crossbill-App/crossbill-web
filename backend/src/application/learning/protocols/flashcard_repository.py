"""Protocol for Flashcard repository in learning context."""

from typing import Protocol

from src.domain.common.value_objects.ids import FlashcardId, UserId
from src.domain.learning.entities.flashcard import Flashcard


class FlashcardRepositoryProtocol(Protocol):
    """Protocol for Flashcard repository operations in learning context."""

    async def find_by_id(self, flashcard_id: FlashcardId, /, user_id: UserId) -> Flashcard | None:
        """
        Find a flashcard by ID with user ownership check.

        Args:
            flashcard_id: The flashcard ID
            user_id: The user ID for ownership verification

        Returns:
            Flashcard entity if found and owned by user, None otherwise
        """
        ...

    async def find_by_id_for_update(
        self, flashcard_id: FlashcardId, user_id: UserId
    ) -> Flashcard | None:
        """Find an owned flashcard and lock it against concurrent changes until it is saved."""
        ...

    async def save(self, flashcard: Flashcard, /) -> Flashcard:
        """
        Save a flashcard entity (create or update).

        Args:
            flashcard: The flashcard entity to save

        Returns:
            Saved flashcard entity with database-generated values
        """
        ...

    async def delete(self, flashcard_id: FlashcardId, /, user_id: UserId) -> bool:
        """
        Delete a flashcard.

        Args:
            flashcard_id: The flashcard ID
            user_id: The user ID for ownership verification

        Returns:
            True if deleted, False if not found
        """
        ...
