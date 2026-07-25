"""
Use case for adding a tag to a highlight by name (get-or-create pattern).
"""

import structlog

from src.application.reading.protocols.highlight_repository import (
    HighlightRepositoryProtocol,
)
from src.application.reading.services.label_resolution_service import LabelResolutionService
from src.application.tagging.protocols.tag_repository import (
    TagRepositoryProtocol,
)
from src.domain.common.exceptions import ValidationError
from src.domain.common.value_objects.ids import BookId, HighlightId, TagId, UserId
from src.domain.learning.entities.flashcard import Flashcard
from src.domain.reading.entities.highlight import Highlight
from src.domain.reading.exceptions import HighlightNotFoundError
from src.domain.reading.services.highlight_style_resolver import ResolvedLabel
from src.domain.tagging.entities.tag import Tag

logger = structlog.get_logger(__name__)


class AddTagToHighlightByNameUseCase:
    """Use case for adding a tag to a highlight by name (get-or-create pattern)."""

    def __init__(
        self,
        highlight_repository: HighlightRepositoryProtocol,
        tag_repository: TagRepositoryProtocol,
        label_resolution_service: LabelResolutionService | None = None,
    ) -> None:
        self.highlight_repository = highlight_repository
        self.tag_repository = tag_repository
        self.label_resolution_service = label_resolution_service

    async def add_tag(
        self, book_id: int, highlight_id: int, tag_name: str, user_id: int
    ) -> tuple[Highlight, list[Flashcard], list[Tag], dict[int, ResolvedLabel]]:
        """
        Add tag by name, creating if it doesn't exist (get-or-create pattern).

        Args:
            book_id: ID of the book
            highlight_id: ID of the highlight
            tag_name: Name of the tag
            user_id: ID of the user

        Returns:
            Tuple of (Highlight, Flashcards, Tags, Labels)

        Raises:
            ValueError: If highlight not found or doesn't belong to book, or tag name is empty
        """
        highlight_id_vo = HighlightId(highlight_id)
        user_id_vo = UserId(user_id)
        book_id_vo = BookId(book_id)

        # Load highlight
        highlight = await self.highlight_repository.find_by_id(highlight_id_vo, user_id_vo)
        if not highlight:
            raise HighlightNotFoundError(highlight_id)

        # Validate tag name
        tag_name = tag_name.strip()
        if not tag_name:
            raise ValidationError("Tag name cannot be empty")

        # Get or create tag
        tag = await self.tag_repository.find_by_book_and_name(book_id_vo, tag_name, user_id_vo)
        if not tag:
            # Create new tag
            tag = Tag.create(
                user_id=user_id_vo,
                book_id=book_id_vo,
                name=tag_name,
            )

        # Use domain entity to validate
        highlight.add_tag(tag.id, tag.book_id)

        # Persist association via repository
        tag = await self.tag_repository.save(tag)
        tag_id_vo = TagId(tag.id.value)
        added = await self.highlight_repository.add_tag_to_highlight(
            highlight_id_vo, tag_id_vo, user_id_vo
        )
        if added:
            logger.info(
                "added_tag_to_highlight_by_name",
                highlight_id=highlight_id,
                tag_id=tag.id.value,
                tag_name=tag_name,
            )

        # Reload with relations
        result = await self.highlight_repository.find_by_id_with_relations(
            highlight_id_vo, user_id_vo
        )
        if not result:
            raise HighlightNotFoundError(highlight_id)
        highlight, flashcards, tags_list = result

        # Resolve labels
        labels: dict[int, ResolvedLabel] = {}
        if self.label_resolution_service is not None:
            labels = await self.label_resolution_service.resolve_for_book(
                user_id_vo, highlight.book_id
            )

        return highlight, flashcards, tags_list, labels
