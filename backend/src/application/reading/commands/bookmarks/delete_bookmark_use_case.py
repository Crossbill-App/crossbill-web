"""Use case for deleting bookmarks."""

import structlog

from src.application.common.ownership import require_book
from src.application.reading.protocols.book_repository import BookRepositoryProtocol
from src.application.reading.protocols.bookmark_repository import BookmarkRepositoryProtocol
from src.domain.common.value_objects.ids import BookId, BookmarkId, UserId

logger = structlog.get_logger(__name__)


class DeleteBookmarkUseCase:
    def __init__(
        self,
        book_repository: BookRepositoryProtocol,
        bookmark_repository: BookmarkRepositoryProtocol,
    ) -> None:
        self.book_repository = book_repository
        self.bookmark_repository = bookmark_repository

    async def delete_bookmark(self, book_id: int, bookmark_id: int, user_id: int) -> None:
        """
        Delete a bookmark (idempotent operation).

        Args:
            book_id: ID of the book (for validation)
            bookmark_id: ID of the bookmark to delete
            user_id: ID of the user

        Raises:
            BookNotFoundError: If book is not found
        """
        # Convert to value objects
        book_id_vo = BookId(book_id)
        bookmark_id_vo = BookmarkId(bookmark_id)
        user_id_vo = UserId(user_id)

        # Validate book exists and belongs to user
        await require_book(self.book_repository, book_id_vo, user_id_vo)

        # Delete bookmark (idempotent)
        deleted = await self.bookmark_repository.delete(bookmark_id_vo, user_id_vo)

        if deleted:
            logger.info("deleted_bookmark", bookmark_id=bookmark_id, book_id=book_id)
        else:
            logger.info(
                "bookmark_not_found_for_deletion",
                bookmark_id=bookmark_id,
                book_id=book_id,
            )
