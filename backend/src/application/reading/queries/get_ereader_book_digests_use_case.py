"""Read use case for the ereader's chapter-digest list."""

from src.application.reading.queries.ereader_digest import (
    EreaderChapterDigestView,
    EreaderDigestQueryProtocol,
)
from src.domain.common.value_objects.ids import UserId
from src.domain.reading.exceptions import BookNotFoundError


class GetEreaderBookDigestsUseCase:
    """Serve every chapter's digest for a book identified by its client id."""

    def __init__(self, ereader_digest_query: EreaderDigestQueryProtocol) -> None:
        self.ereader_digest_query = ereader_digest_query

    async def get_digests_for_client_book(
        self, client_book_id: str, user_id: UserId
    ) -> tuple[EreaderChapterDigestView, ...]:
        """Get ereader-friendly digest for every chapter that has it.

        Chapters come back in chapter-number order, and chapters without
        a digest are omitted.

        Raises:
            BookNotFoundError: If no book matches client_book_id for the user.
        """
        items = await self.ereader_digest_query.list_for_client_book(client_book_id, user_id)
        if items is None:
            raise BookNotFoundError(client_book_id)
        return items
