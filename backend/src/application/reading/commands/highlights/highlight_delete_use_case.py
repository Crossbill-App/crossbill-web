from src.application.common.ownership import require_book
from src.application.reading.protocols.book_repository import BookRepositoryProtocol
from src.application.reading.protocols.highlight_repository import HighlightRepositoryProtocol
from src.domain.common.value_objects import BookId, HighlightId, UserId


class HighlightDeleteUseCase:
    def __init__(
        self,
        book_repository: BookRepositoryProtocol,
        highlight_repository: HighlightRepositoryProtocol,
    ) -> None:
        self.book_repository = book_repository
        self.highlight_repository = highlight_repository

    async def delete_highlights(self, book_id: int, highlight_ids: list[int], user_id: int) -> int:
        """
        Soft delete highlights from a book.

        This performs a soft delete by marking the highlights as deleted.
        When syncing highlights, deleted highlights will not be recreated,
        ensuring that user deletions persist across syncs.

        Also cascades to delete all bookmarks and flashcards associated with
        the deleted highlights.

        Args:
            book_id: ID of the book
            highlight_ids: List of highlight IDs to delete
            user_id: ID of the user

        Returns:
            Number of highlights deleted

        Raises:
            BookNotFoundError: If book is not found
        """
        # Convert primitives to value objects
        book_id_vo = BookId(book_id)
        user_id_vo = UserId(user_id)
        highlight_ids_vo = [HighlightId(hid) for hid in highlight_ids]

        # Verify book exists
        await require_book(self.book_repository, book_id_vo, user_id_vo)

        # Soft delete highlights (cascades to bookmarks and flashcards)
        return await self.highlight_repository.soft_delete_by_ids(
            highlight_ids=highlight_ids_vo,
            user_id=user_id_vo,
            book_id=book_id_vo,
        )
