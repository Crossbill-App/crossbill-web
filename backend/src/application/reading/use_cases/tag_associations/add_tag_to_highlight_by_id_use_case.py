"""
Use case for adding an existing tag to a highlight by ID.
"""

import structlog

from src.application.reading.protocols.highlight_repository import (
    HighlightRepositoryProtocol,
)
from src.application.reading.services.label_resolution_service import LabelResolutionService
from src.application.tagging.protocols.tag_repository import (
    TagRepositoryProtocol,
)
from src.domain.common.value_objects.ids import HighlightId, TagId, UserId
from src.domain.learning.entities.flashcard import Flashcard
from src.domain.reading.entities.highlight import Highlight
from src.domain.reading.exceptions import HighlightNotFoundError
from src.domain.reading.services.highlight_style_resolver import ResolvedLabel
from src.domain.tagging.entities.tag import Tag
from src.domain.tagging.exceptions import TagNotFoundError

logger = structlog.get_logger(__name__)


class AddTagToHighlightByIdUseCase:
    """Use case for adding an existing tag to a highlight by ID."""

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
        self, highlight_id: int, tag_id: int, user_id: int
    ) -> tuple[Highlight, list[Flashcard], list[Tag], dict[int, ResolvedLabel]]:
        """
        Add an existing tag to a highlight.

        Args:
            highlight_id: ID of the highlight
            tag_id: ID of the tag to add
            user_id: ID of the user

        Returns:
            Tuple of (Highlight, Flashcards, Tags, Labels)

        Raises:
            ValueError: If highlight or tag not found
        """
        highlight_id_vo = HighlightId(highlight_id)
        tag_id_vo = TagId(tag_id)
        user_id_vo = UserId(user_id)

        # Load entities
        highlight = await self.highlight_repository.find_by_id(highlight_id_vo, user_id_vo)
        if not highlight:
            raise HighlightNotFoundError(highlight_id)

        tag = await self.tag_repository.find_by_id(tag_id_vo, user_id_vo)
        if not tag:
            raise TagNotFoundError(tag_id)

        # Use domain entity to validate
        highlight.add_tag(tag.id, tag.book_id)

        # Persist association via repository
        added = await self.highlight_repository.add_tag_to_highlight(
            highlight_id_vo, tag_id_vo, user_id_vo
        )
        if added:
            logger.info("added_tag_to_highlight", highlight_id=highlight_id, tag_id=tag_id)

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
