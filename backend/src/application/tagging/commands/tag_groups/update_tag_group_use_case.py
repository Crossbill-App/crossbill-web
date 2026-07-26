"""
Use case for updating a tag group's name.
"""

import structlog

from src.application.common.ownership import require_book
from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.tagging.protocols.tag_repository import (
    TagRepositoryProtocol,
)
from src.domain.common.value_objects.ids import BookId, TagGroupId, UserId
from src.domain.tagging.entities.tag_group import TagGroup
from src.domain.tagging.exceptions import (
    DuplicateTagGroupNameError,
    TagGroupNotFoundError,
)

logger = structlog.get_logger(__name__)


class UpdateTagGroupUseCase:
    """Use case for updating a tag group's name."""

    def __init__(
        self,
        tag_repository: TagRepositoryProtocol,
        book_repository: BookRepositoryProtocol,
    ) -> None:
        self.tag_repository = tag_repository
        self.book_repository = book_repository

    async def update_group(
        self, group_id: int, book_id: int, new_name: str, user_id: int
    ) -> TagGroup:
        """
        Update a tag group's name.

        Args:
            group_id: ID of the group
            book_id: ID of the book
            new_name: New name for the group
            user_id: ID of the user

        Returns:
            Updated group entity

        Raises:
            BookNotFoundError: If book not found
            TagGroupNotFoundError: If group not found
            DuplicateTagGroupNameError: If new name already exists
        """
        group_id_vo = TagGroupId(group_id)
        book_id_vo = BookId(book_id)
        user_id_vo = UserId(user_id)

        await require_book(self.book_repository, book_id_vo, user_id_vo)

        # Load group and verify it belongs to the correct book
        group = await self.tag_repository.find_group_by_id(group_id_vo, book_id_vo)
        if not group:
            raise TagGroupNotFoundError(group_id)

        # Check for duplicate (if name changed)
        if new_name.strip() != group.name:
            existing = await self.tag_repository.find_group_by_name(book_id_vo, new_name.strip())
            if existing:
                raise DuplicateTagGroupNameError(new_name)

        group.rename(new_name)
        group = await self.tag_repository.save_group(group)

        logger.info("updated_tag_group", group_id=group_id, new_name=new_name)
        return group
