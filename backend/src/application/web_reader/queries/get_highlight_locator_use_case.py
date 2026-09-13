"""Read use case for one highlight's stored locator."""

from src.application.web_reader.queries.highlight_locators import (
    HighlightLocatorQueryProtocol,
    HighlightLocatorView,
    locator_view,
)
from src.domain.common.value_objects.ids import HighlightId, UserId
from src.domain.reading.exceptions import HighlightNotFoundError


class GetHighlightLocatorUseCase:
    """Answer where one live highlight is, or why it cannot be said."""

    def __init__(self, highlight_locator_query: HighlightLocatorQueryProtocol) -> None:
        self.highlight_locator_query = highlight_locator_query

    async def get_highlight_locator(
        self, highlight_id: HighlightId, user_id: UserId
    ) -> HighlightLocatorView:
        """Return where the highlight is, or why that cannot be said.

        Raises:
            HighlightNotFoundError: If the user has no live highlight with that id.
        """
        stored = await self.highlight_locator_query.locator_for_highlight(highlight_id, user_id)
        if stored is None:
            raise HighlightNotFoundError(highlight_id.value)
        return locator_view(stored.highlight, stored.publication_hash)
