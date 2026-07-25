"""
Use case for updating a tag's group association.
"""

import structlog

from src.application.common.ownership import require_belongs_to_book
from src.application.reading.protocols.tag_repository import (
    TagRepositoryProtocol,
)
from src.domain.common.value_objects.ids import (
    BookId,
    TagGroupId,
    TagId,
    UserId,
)
from src.domain.tagging.entities.tag import Tag
from src.domain.tagging.exceptions import TagGroupNotFoundError, TagNotFoundError

logger = structlog.get_logger(__name__)


class UpdateTagGroupAssociationUseCase:
    """Use case for updating a tag's group association."""

    def __init__(
        self,
        tag_repository: TagRepositoryProtocol,
    ) -> None:
        self.tag_repository = tag_repository

    async def update_association(
        self, book_id: int, tag_id: int, group_id: int | None, user_id: int
    ) -> Tag:
        """
        Update a tag's group association.

        Args:
            book_id: ID of the book
            tag_id: ID of the tag
            group_id: ID of the group (or None to clear association)
            user_id: ID of the user

        Returns:
            Updated tag entity

        Raises:
            ValueError: If tag, group, or book not found, or if they don't match
        """
        tag_id_vo = TagId(tag_id)
        user_id_vo = UserId(user_id)
        book_id_vo = BookId(book_id)
        group_id_vo = TagGroupId(group_id) if group_id else None

        tag = await self.tag_repository.find_by_id(tag_id_vo, user_id_vo)
        if not tag:
            raise TagNotFoundError(tag_id)

        # A tag from another book is indistinguishable from a missing one.
        require_belongs_to_book(tag, book_id_vo, lambda: TagNotFoundError(tag_id))

        # Validate group if provided
        if group_id_vo:
            group = await self.tag_repository.find_group_by_id(group_id_vo, book_id_vo)
            if not group:
                raise TagGroupNotFoundError(group_id_vo.value)

        tag.update_group(group_id_vo)
        tag = await self.tag_repository.save(tag)

        logger.info("updated_tag_group_association", tag_id=tag_id, group_id=group_id)
        return tag
