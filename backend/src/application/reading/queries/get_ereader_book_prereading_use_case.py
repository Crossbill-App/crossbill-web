"""Read use case for the ereader's chapter-prereading list."""

from src.application.reading.queries.ereader_prereading import (
    EreaderChapterPrereadingView,
    EreaderPrereadingQueryProtocol,
)
from src.domain.common.value_objects.ids import UserId
from src.domain.reading.exceptions import BookNotFoundError


class GetEreaderBookPrereadingUseCase:
    """Serve every chapter's prereading for a book identified by its client id."""

    def __init__(self, ereader_prereading_query: EreaderPrereadingQueryProtocol) -> None:
        self.ereader_prereading_query = ereader_prereading_query

    async def get_prereading_for_client_book(
        self, client_book_id: str, user_id: UserId
    ) -> tuple[EreaderChapterPrereadingView, ...]:
        """Get ereader-friendly prereading for every chapter that has it.

        Chapters come back in chapter-number order, and chapters without
        prereading content are omitted.

        Raises:
            BookNotFoundError: If no book matches client_book_id for the user.
        """
        items = await self.ereader_prereading_query.list_for_client_book(client_book_id, user_id)
        if items is None:
            raise BookNotFoundError(client_book_id)
        return items
