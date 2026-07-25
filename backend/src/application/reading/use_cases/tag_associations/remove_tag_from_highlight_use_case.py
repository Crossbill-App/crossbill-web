"""
Use case for removing a tag from a highlight.
"""

import structlog

from src.application.reading.protocols.highlight_repository import (
    HighlightRepositoryProtocol,
)
from src.application.reading.services.label_resolution_service import LabelResolutionService
from src.domain.common.value_objects.ids import HighlightId, TagId, UserId
from src.domain.learning.entities.flashcard import Flashcard
from src.domain.reading.entities.highlight import Highlight
from src.domain.reading.exceptions import HighlightNotFoundError
from src.domain.reading.services.highlight_style_resolver import ResolvedLabel
from src.domain.tagging.entities.tag import Tag

logger = structlog.get_logger(__name__)


class RemoveTagFromHighlightUseCase:
    """Use case for removing a tag from a highlight."""

    def __init__(
        self,
        highlight_repository: HighlightRepositoryProtocol,
        label_resolution_service: LabelResolutionService | None = None,
    ) -> None:
        self.highlight_repository = highlight_repository
        self.label_resolution_service = label_resolution_service

    async def remove_tag(
        self, highlight_id: int, tag_id: int, user_id: int
    ) -> tuple[Highlight, list[Flashcard], list[Tag], dict[int, ResolvedLabel]]:
        """
        Remove a tag from a highlight.

        Args:
            highlight_id: ID of the highlight
            tag_id: ID of the tag to remove
            user_id: ID of the user

        Returns:
            Tuple of (Highlight, Flashcards, Tags, Labels)

        Raises:
            NotFoundError: If highlight not found
        """
        highlight_id_vo = HighlightId(highlight_id)
        tag_id_vo = TagId(tag_id)
        user_id_vo = UserId(user_id)

        # Load highlight
        highlight = await self.highlight_repository.find_by_id(highlight_id_vo, user_id_vo)
        if not highlight:
            raise HighlightNotFoundError(highlight_id)

        # Remove association via repository
        removed = await self.highlight_repository.remove_tag_from_highlight(
            highlight_id_vo, tag_id_vo, user_id_vo
        )
        if removed:
            logger.info("removed_tag_from_highlight", highlight_id=highlight_id, tag_id=tag_id)

        # Reload with relations
        result = await self.highlight_repository.find_by_id_with_relations(
            highlight_id_vo, user_id_vo
        )
        if not result:
            raise HighlightNotFoundError(highlight_id)
        highlight, flashcards, tags = result

        # Resolve labels
        labels: dict[int, ResolvedLabel] = {}
        if self.label_resolution_service is not None:
            labels = await self.label_resolution_service.resolve_for_book(
                user_id_vo, highlight.book_id
            )

        return highlight, flashcards, tags, labels
