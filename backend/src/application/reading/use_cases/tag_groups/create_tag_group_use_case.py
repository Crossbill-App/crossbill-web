"""
Use case for creating a new tag group.
"""

import structlog

from src.application.common.ownership import require_book
from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.reading.protocols.tag_repository import (
    TagRepositoryProtocol,
)
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.tagging.entities.tag_group import TagGroup
from src.domain.tagging.exceptions import DuplicateTagGroupNameError

logger = structlog.get_logger(__name__)


class CreateTagGroupUseCase:
    """Use case for creating a new tag group."""

    def __init__(
        self,
        tag_repository: TagRepositoryProtocol,
        book_repository: BookRepositoryProtocol,
    ) -> None:
        self.tag_repository = tag_repository
        self.book_repository = book_repository

    async def create_group(self, book_id: int, name: str, user_id: int) -> TagGroup:
        """
        Create a new tag group.

        Args:
            book_id: ID of the book
            name: Name of the group
            user_id: ID of the user

        Returns:
            Created group entity

        Raises:
            BookNotFoundError: If book not found
            DuplicateTagGroupNameError: If group with same name already exists
        """
        book_id_vo = BookId(book_id)
        user_id_vo = UserId(user_id)

        # Validate book exists
        await require_book(self.book_repository, book_id_vo, user_id_vo)

        # Check for duplicate name
        existing = await self.tag_repository.find_group_by_name(book_id_vo, name.strip())
        if existing:
            raise DuplicateTagGroupNameError(name)

        group = TagGroup.create(book_id=book_id_vo, name=name)
        group = await self.tag_repository.save_group(group)

        logger.info("created_tag_group", group_id=group.id.value, book_id=book_id)
        return group
