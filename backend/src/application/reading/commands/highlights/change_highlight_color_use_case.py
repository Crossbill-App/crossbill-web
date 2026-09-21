"""Change which highlighter one highlight was marked with."""

import structlog

from src.application.common.ownership import require_book
from src.application.reading.protocols.book_repository import BookRepositoryProtocol
from src.application.reading.protocols.highlight_repository import HighlightRepositoryProtocol
from src.application.reading.protocols.highlight_style_repository import (
    HighlightStyleRepositoryProtocol,
)
from src.application.reading.services.label_resolution_service import LabelResolutionService
from src.domain.common.value_objects import BookId, HighlightId, UserId
from src.domain.reading.entities.highlight import Highlight
from src.domain.reading.entities.highlight_style import KOREADER_DEFAULT_DRAWER
from src.domain.reading.exceptions import HighlightNotFoundError
from src.domain.reading.services.highlight_style_resolver import ResolvedLabel

logger = structlog.get_logger(__name__)


class ChangeHighlightColorUseCase:
    """File one highlight under the book's style for another KOReader colour.

    The colour a passage is drawn in belongs to the highlight, where the label
    naming that colour belongs to the style -- and the style is shared with every
    other highlight of the same colour in the book. So this repoints the one
    highlight at another style rather than recolouring the style it was under,
    which would repaint all of them.

    The style for the chosen colour is created on the spot when the book has none,
    exactly as making a highlight in that colour creates it.
    """

    def __init__(
        self,
        book_repository: BookRepositoryProtocol,
        highlight_repository: HighlightRepositoryProtocol,
        highlight_style_repository: HighlightStyleRepositoryProtocol,
        label_resolution_service: LabelResolutionService,
    ) -> None:
        self.book_repository = book_repository
        self.highlight_repository = highlight_repository
        self.highlight_style_repository = highlight_style_repository
        self.label_resolution_service = label_resolution_service

    async def execute(
        self,
        book_id: int,
        highlight_id: int,
        user_id: int,
        device_color: str,
        device_style: str | None = None,
    ) -> tuple[Highlight, ResolvedLabel | None]:
        """Draw one highlight in another colour, and say what it now resolves to.

        Args:
            book_id: The book the highlight is in.
            highlight_id: The highlight to recolour.
            user_id: Whose highlight it is.
            device_color: A KOReader colour name, such as ``red``.
            device_style: The drawer that colour is drawn with, KOReader's own
                default when it is omitted.

        Returns:
            The stored highlight and the label its new style resolves to, which is
            ``None`` only for a style that resolution does not reach.

        Raises:
            BookNotFoundError: If the user has no such book.
            HighlightNotFoundError: If the book holds no such live highlight.
        """
        user = UserId(user_id)
        book = BookId(book_id)
        await require_book(self.book_repository, book, user)

        highlight = await self.highlight_repository.find_by_id(HighlightId(highlight_id), user)
        # A highlight of another book is as good as missing: from here the two
        # are indistinguishable, which is the answer a wrong book_id deserves.
        if highlight is None or highlight.book_id != book or highlight.is_deleted():
            raise HighlightNotFoundError(highlight_id)

        style = await self.highlight_style_repository.find_or_create(
            user, book, device_color, device_style or KOREADER_DEFAULT_DRAWER
        )
        highlight.file_under(style.id)
        saved = await self.highlight_repository.save(highlight)

        logger.info(
            "highlight_recoloured",
            book_id=book_id,
            highlight_id=highlight_id,
            device_color=device_color,
            highlight_style_id=style.id.value,
        )

        resolved = await self.label_resolution_service.resolve_for_book(user, book)
        return saved, resolved.get(style.id.value)
