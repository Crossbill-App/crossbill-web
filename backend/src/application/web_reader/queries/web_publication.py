"""Read model for the Web Publication Manifest view.

The view DTO is
:class:`~src.application.web_reader.publications.ParsedPublication` itself: the
manifest renders an EPUB's own structure and adds nothing from the database, so
a second set of dataclasses restating it would only be a mapping step. Like any
read model it is a dead end -- it is rendered, never fed back into a command.
See ``docs/adr/0001-read-models-and-query-services.md``.
"""

from typing import Protocol

from src.application.web_reader.publications import ParsedPublication
from src.domain.common.value_objects.ids import BookId, UserId


class WebPublicationQueryProtocol(Protocol):
    """Port for reading a book's publication structure out of its stored EPUB."""

    async def get_web_publication(
        self, book_id: BookId, user_id: UserId
    ) -> ParsedPublication | None:
        """Return the publication for a user's book, or ``None`` when they have no such book.

        The book's own title stands in when the EPUB's package document states
        none, so the manifest always has one to render.

        Raises:
            EbookFileNotFoundError: If the book exists but no EPUB is stored for
                it -- distinct from ``None``, which means the book does not.
            InvalidEbookError: If the stored EPUB cannot be parsed.
        """
        ...
