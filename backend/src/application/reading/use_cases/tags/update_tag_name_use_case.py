"""Use case for updating tag names."""

import structlog

from src.application.common.ownership import require_belongs_to_book
from src.application.reading.protocols.tag_repository import (
    TagRepositoryProtocol,
)
from src.domain.common.value_objects.ids import BookId, TagId, UserId
from src.domain.tagging.entities.tag import Tag
from src.domain.tagging.exceptions import DuplicateTagNameError, TagNotFoundError

logger = structlog.get_logger(__name__)


class UpdateTagNameUseCase:
    """Use case for updating tag names."""

    def __init__(
        self,
        tag_repository: TagRepositoryProtocol,
    ) -> None:
        self.tag_repository = tag_repository

    async def update_tag_name(self, book_id: int, tag_id: int, new_name: str, user_id: int) -> Tag:
        """
        Update a tag's name.

        Args:
            book_id: ID of the book
            tag_id: ID of the tag to update
            new_name: New name for the tag
            user_id: ID of the user

        Returns:
            Updated tag entity

        Raises:
            TagNotFoundError: If tag not found or belongs to another book
            DuplicateTagNameError: If new name already exists
        """
        tag_id_vo = TagId(tag_id)
        user_id_vo = UserId(user_id)
        book_id_vo = BookId(book_id)

        tag = await self.tag_repository.find_by_id(tag_id_vo, user_id_vo)
        if not tag:
            raise TagNotFoundError(tag_id)

        require_belongs_to_book(tag, book_id_vo, lambda: TagNotFoundError(tag_id))

        if new_name.strip() != tag.name:
            existing = await self.tag_repository.find_by_book_and_name(
                book_id_vo, new_name.strip(), user_id_vo
            )
            if existing:
                raise DuplicateTagNameError(new_name)

        tag.rename(new_name)
        tag = await self.tag_repository.save(tag)

        logger.info("updated_tag_name", tag_id=tag_id, new_name=new_name)
        return tag
