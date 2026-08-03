import structlog

from src.application.common.ownership import require_book
from src.application.reading.protocols.book_repository import BookRepositoryProtocol
from src.application.reading.protocols.highlight_repository import HighlightRepositoryProtocol
from src.application.semantic.content_type import ContentType
from src.application.semantic.protocols.embedding_repository import EmbeddingRepositoryProtocol
from src.domain.common.value_objects import BookId, HighlightId, UserId

logger = structlog.get_logger(__name__)


class HighlightDeleteUseCase:
    def __init__(
        self,
        book_repository: BookRepositoryProtocol,
        highlight_repository: HighlightRepositoryProtocol,
        embedding_repository: EmbeddingRepositoryProtocol,
    ) -> None:
        self.book_repository = book_repository
        self.highlight_repository = highlight_repository
        self._embedding_repository = embedding_repository

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
        deleted_ids = await self.highlight_repository.soft_delete_by_ids(
            highlight_ids=highlight_ids_vo,
            user_id=user_id_vo,
            book_id=book_id_vo,
        )

        await self._delete_embeddings_for(deleted_ids)

        return len(deleted_ids)

    async def _delete_embeddings_for(self, deleted_ids: list[HighlightId]) -> None:
        """Remove the embeddings of highlights this call actually soft deleted.

        A soft delete is an UPDATE, so no foreign key cascades the embeddings
        away; they have to be removed here. Only the IDs the repository
        confirmed — the requested IDs are unverified and could name another
        user's highlight, whose embedding must not be touched.

        The soft delete has already committed by now, and the two are not one
        transaction, so a failure here must not fail the user's delete. Log it
        and let the backfill sweep reconcile, as the enqueue seam does.
        """
        if not deleted_ids:
            return

        content_ids = [hid.value for hid in deleted_ids]
        try:
            # One statement for the whole batch rather than a job each.
            await self._embedding_repository.delete_for(ContentType.HIGHLIGHT, content_ids)
        except Exception:
            logger.exception("failed_to_delete_highlight_embeddings", highlight_ids=content_ids)
