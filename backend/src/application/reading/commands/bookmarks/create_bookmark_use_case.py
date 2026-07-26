"""Use case for creating bookmarks."""

import structlog

from src.application.common.ownership import require_belongs_to_book, require_book
from src.application.reading.protocols.book_repository import BookRepositoryProtocol
from src.application.reading.protocols.bookmark_repository import BookmarkRepositoryProtocol
from src.application.reading.protocols.highlight_repository import HighlightRepositoryProtocol
from src.domain.common.value_objects.ids import BookId, HighlightId, UserId
from src.domain.reading.entities.bookmark import Bookmark
from src.domain.reading.exceptions import HighlightNotFoundError

logger = structlog.get_logger(__name__)


class CreateBookmarkUseCase:
    def __init__(
        self,
        book_repository: BookRepositoryProtocol,
        bookmark_repository: BookmarkRepositoryProtocol,
        highlight_repository: HighlightRepositoryProtocol,
    ) -> None:
        self.book_repository = book_repository
        self.bookmark_repository = bookmark_repository
        self.highlight_repository = highlight_repository

    async def create_bookmark(self, book_id: int, highlight_id: int, user_id: int) -> Bookmark:
        """
        Create a new bookmark for a highlight.

        Args:
            book_id: ID of the book
            highlight_id: ID of the highlight to bookmark
            user_id: ID of the user

        Returns:
            Created bookmark (or existing if already exists)

        Raises:
            BookNotFoundError: If book is not found
            HighlightNotFoundError: If highlight doesn't exist or belongs to another book
        """
        # Convert to value objects
        book_id_vo = BookId(book_id)
        highlight_id_vo = HighlightId(highlight_id)
        user_id_vo = UserId(user_id)

        # Validate book exists and belongs to user
        await require_book(self.book_repository, book_id_vo, user_id_vo)

        # Validate highlight exists and belongs to user
        highlight = await self.highlight_repository.find_by_id(highlight_id_vo, user_id_vo)
        if not highlight:
            raise HighlightNotFoundError(highlight_id)

        # A highlight from another book is indistinguishable from a missing one.
        require_belongs_to_book(highlight, book_id_vo, lambda: HighlightNotFoundError(highlight_id))

        # Check if bookmark already exists (idempotent)
        existing = await self.bookmark_repository.find_by_book_and_highlight(
            book_id_vo, highlight_id_vo
        )
        if existing:
            logger.info(
                "bookmark_already_exists",
                book_id=book_id,
                highlight_id=highlight_id,
                bookmark_id=existing.id.value,
            )
            return existing

        # Create new bookmark
        bookmark = Bookmark.create(book_id=book_id_vo, highlight_id=highlight_id_vo)
        bookmark = await self.bookmark_repository.save(bookmark)

        logger.info(
            "created_bookmark",
            bookmark_id=bookmark.id.value,
            book_id=book_id,
            highlight_id=highlight_id,
        )
        return bookmark
