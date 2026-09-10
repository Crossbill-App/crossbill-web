"""Port for the publication index stored beside a book."""

from typing import Protocol

from src.application.web_reader.publications import ParsedPublication
from src.domain.common.value_objects.ids import BookId, UserId


class PublicationRepositoryProtocol(Protocol):
    """Holds one derived publication index per book, keyed by the book.

    ``save`` carries the file name because a ``ParsedPublication`` does not: the
    index describes the EPUB's contents, not where the EPUB itself is stored.
    """

    async def get(self, book_id: BookId, user_id: UserId) -> ParsedPublication | None: ...

    async def save(
        self, book_id: BookId, file_name: str, publication: ParsedPublication
    ) -> None: ...

    async def delete(self, book_id: BookId) -> None: ...
