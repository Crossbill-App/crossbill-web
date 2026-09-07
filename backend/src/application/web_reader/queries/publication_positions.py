"""Read model for a publication's position list, served to the web reader.

The manifest (M1.1) links a position list; this is the view behind that link. A
*position* is Readium's unit of "how far through the book am I" for a format
that has no pages of its own: the reading order is cut into equal-sized pieces,
and a locator names each one. It is a dead end like any read model -- rendered
into an HTTP response and never fed back into a command. See
``docs/adr/0001-read-models-and-query-services.md``.
"""

from dataclasses import dataclass
from typing import Protocol

from src.domain.common.value_objects.ids import BookId, UserId


@dataclass(frozen=True)
class PublicationPosition:
    """One position in a publication, as a Readium Locator carries it.

    Attributes:
        href: The resource this position falls in, as a path inside the EPUB
            container -- the same form
            :class:`~src.application.web_reader.publications.PublicationResource`
            uses, so the router points it at the resource endpoint the same way.
        media_type: The media type the publication declares for that resource.
        position: The position's 1-based number, counted across the whole
            publication rather than restarted per resource.
        progression: How far into its own resource this position begins, in
            ``[0, 1)``.
        total_progression: How far into the whole publication it begins, in
            ``[0, 1)``.
    """

    href: str
    media_type: str
    position: int
    progression: float
    total_progression: float


class PublicationPositionsQueryProtocol(Protocol):
    """Port for computing a book's position list from its stored EPUB."""

    async def get_publication_positions(
        self, book_id: BookId, user_id: UserId
    ) -> tuple[PublicationPosition, ...] | None:
        """Return the positions of a user's publication, or ``None`` for no such book.

        Never empty when it is not ``None``: a publication with nothing in its
        reading order fails to parse at all, so an empty tuple could not mean
        "this book has no positions" and does not have to be told apart from
        "there is no such book".

        Raises:
            EbookFileNotFoundError: If the book exists but no EPUB is stored for
                it -- distinct from ``None``, which means the book does not.
            InvalidEbookError: If the stored EPUB cannot be parsed.
        """
        ...
