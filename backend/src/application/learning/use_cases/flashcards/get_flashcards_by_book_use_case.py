"""Use case for retrieving flashcards by book."""

from src.application.common.ownership import require_book
from src.application.learning.protocols.flashcard_repository import FlashcardRepositoryProtocol
from src.application.learning.use_cases.dtos import FlashcardWithHighlight
from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.reading.protocols.highlight_repository import HighlightRepositoryProtocol
from src.application.reading.services.label_resolution_service import LabelResolutionService
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.library.entities.chapter import Chapter
from src.domain.reading.entities.highlight import Highlight
from src.domain.reading.services.highlight_style_resolver import ResolvedLabel
from src.domain.tagging.entities.tag import Tag


class GetFlashcardsByBookUseCase:
    """Use case for retrieving flashcards by book."""

    def __init__(
        self,
        flashcard_repository: FlashcardRepositoryProtocol,
        book_repository: BookRepositoryProtocol,
        highlight_repository: HighlightRepositoryProtocol,
        label_resolution_service: LabelResolutionService | None = None,
    ) -> None:
        """Initialize use case with repository protocols."""
        self.flashcard_repository = flashcard_repository
        self.book_repository = book_repository
        self.highlight_repository = highlight_repository
        self.label_resolution_service = label_resolution_service

    async def get_flashcards(
        self, book_id: int, user_id: int
    ) -> tuple[list[FlashcardWithHighlight], dict[int, ResolvedLabel]]:
        """
        Get all flashcards for a book with their associated highlights.

        Args:
            book_id: ID of the book
            user_id: ID of the user

        Returns:
            Tuple of (FlashcardWithHighlight DTOs, resolved labels)

        Raises:
            BookNotFoundError: If book is not found
        """
        book_id_vo = BookId(book_id)
        user_id_vo = UserId(user_id)

        await require_book(self.book_repository, book_id_vo, user_id_vo)

        flashcards = await self.flashcard_repository.find_by_book(book_id_vo, user_id_vo)

        highlight_ids = [fc.highlight_id for fc in flashcards if fc.highlight_id is not None]

        highlight_map: dict[int, tuple[Highlight, Chapter | None, list[Tag]]] = {}
        if highlight_ids:
            highlights_data = await self.highlight_repository.find_by_ids_with_tags(
                highlight_ids, user_id_vo
            )
            highlight_map = {h.id.value: (h, chapter, tags) for h, chapter, tags in highlights_data}

        # Combine flashcards with their highlights
        result = []
        for fc in flashcards:
            highlight = None
            chapter = None
            tags = []
            if fc.highlight_id:
                highlight_data = highlight_map.get(fc.highlight_id.value)
                if highlight_data:
                    highlight, chapter, tags = highlight_data

            result.append(
                FlashcardWithHighlight(
                    flashcard=fc, highlight=highlight, chapter=chapter, tags=tags
                )
            )

        # Resolve labels
        labels: dict[int, ResolvedLabel] = {}
        if self.label_resolution_service is not None:
            labels = await self.label_resolution_service.resolve_for_book(user_id_vo, book_id_vo)

        return result, labels
