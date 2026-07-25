"""
Book-scoped highlight search.

Provides full-text search within a specific book's highlights.
"""

from src.application.common.ownership import require_book
from src.application.reading.protocols.book_repository import BookRepositoryProtocol
from src.application.reading.protocols.highlight_repository import HighlightRepositoryProtocol
from src.application.reading.services.label_resolution_service import LabelResolutionService
from src.domain.common.value_objects import BookId, UserId
from src.domain.reading.services.highlight_grouping_service import (
    ChapterWithHighlights,
    HighlightGroupingService,
)
from src.domain.reading.services.highlight_style_resolver import ResolvedLabel
from src.domain.tagging.entities.tag import Tag


class HighlightSearchUseCase:
    def __init__(
        self,
        book_repository: BookRepositoryProtocol,
        highlight_repository: HighlightRepositoryProtocol,
        label_resolution_service: LabelResolutionService | None = None,
    ) -> None:
        self.book_repository = book_repository
        self.highlight_repository = highlight_repository
        self.highlight_grouping_service = HighlightGroupingService()
        self.label_resolution_service = label_resolution_service

    async def search_book_highlights(
        self, book_id: int, user_id: int, search_text: str, limit: int = 100
    ) -> tuple[list[ChapterWithHighlights[Tag]], int, dict[int, ResolvedLabel]]:
        """
        Search for highlights within a specific book using full-text search.

        Results are grouped by chapter, with only chapters containing
        matching highlights included in the response.

        Args:
            book_id: ID of the book to search within
            user_id: ID of the user
            search_text: Text to search for
            limit: Maximum number of results to return

        Returns:
            Tuple of (chapters with highlights, total highlight count, resolved labels)

        Raises:
            BookNotFoundError: If book is not found or doesn't belong to user
        """
        # Convert primitives to value objects
        book_id_vo = BookId(book_id)
        user_id_vo = UserId(user_id)

        # Verify book exists and belongs to user
        await require_book(self.book_repository, book_id_vo, user_id_vo)

        # Search highlights (returns domain entities)
        highlights_with_context = await self.highlight_repository.search(
            search_text=search_text,
            user_id=user_id_vo,
            book_id=book_id_vo,
            limit=limit,
        )

        # Use domain service to group highlights by chapter
        grouped = self.highlight_grouping_service.group_by_chapter(
            [(h, c, tags, flashcards) for h, _, c, tags, flashcards in highlights_with_context]
        )

        # Calculate total number of highlights
        total = sum(len(chapter_group.highlights) for chapter_group in grouped)

        # Resolve labels
        labels: dict[int, ResolvedLabel] = {}
        if self.label_resolution_service is not None:
            labels = await self.label_resolution_service.resolve_for_book(user_id_vo, book_id_vo)

        return (grouped, total, labels)
