"""Use case for getting tags for a book."""

from src.application.common.ownership import require_book
from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.tagging.protocols.tag_repository import (
    TagRepositoryProtocol,
)
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.tagging.entities.tag import Tag


class GetTagsForBookUseCase:
    """Use case for getting tags for a book."""

    def __init__(
        self,
        tag_repository: TagRepositoryProtocol,
        book_repository: BookRepositoryProtocol,
    ) -> None:
        self.tag_repository = tag_repository
        self.book_repository = book_repository

    async def get_tags(self, book_id: int, user_id: int) -> list[Tag]:
        """
        Get all tags for a book.

        Args:
            book_id: ID of the book
            user_id: ID of the user

        Returns:
            List of tag entities

        Raises:
            NotFoundError: If book not found
        """
        book_id_vo = BookId(book_id)
        user_id_vo = UserId(user_id)

        await require_book(self.book_repository, book_id_vo, user_id_vo)

        return await self.tag_repository.find_by_book(book_id_vo, user_id_vo)
