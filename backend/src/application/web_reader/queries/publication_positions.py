"""Read model for a publication's position list, served to the web reader.

The manifest (M1.1) links a position list; this is the view behind that link. A
*position* is Readium's unit of "how far through the book am I" for a format
that has no pages of its own: the reading order is cut into equal-sized pieces,
and a locator names each one.

Read-model rules apply as they do to every view here
(``docs/adr/0001-read-models-and-query-services.md``): this is rendered and then
it is finished with.
"""

from dataclasses import dataclass
from typing import Protocol

from src.domain.common.value_objects.ids import BookId, UserId

# Bytes of a reflowable document per position, which is the length every Readium
# toolkit uses (readium/architecture#123). The number is arbitrary and the
# agreement is not: a locator saying "position 42" means nothing unless whoever
# reads it cut the book the same way whoever wrote it did.
POSITION_LENGTH = 1024

# The most positions one publication may be cut into.
#
# This endpoint is the one place in the web reader where a small file can ask
# for an enormous answer. Everywhere else the response is bounded by bytes that
# actually exist: a resource is a member that has to be decompressed, so the
# archive has to carry it. A position list is arithmetic over sizes the central
# directory *declares*, and a declaration costs four bytes to write -- so a
# 1.3 KB archive can claim a two-gigabyte chapter and ask for two million
# positions, each of which becomes a dataclass, a Pydantic model and a JSON
# object on the way out.
#
# `check_member_is_servable` bounds each member at `MAX_RESOURCE_BYTES`, which
# is 64 MiB and so 65,536 positions. That is not enough on its own: the parser
# admits a publication declaring `MAX_PUBLICATION_UNCOMPRESSED_BYTES` in total,
# and thirty-two members just under the per-member cap still add up to two
# million positions. The per-member cap bounds one member; this bounds the sum.
#
# The size is derived from the upload limit rather than picked. An EPUB arrives
# as at most the 50 MiB `MAX_EBOOK_SIZE` an upload may be, and XHTML deflates at
# roughly four to one, so four times the upload cap is a generous ceiling on the
# markup an honest reading order can hold. For scale: the longest novel ever
# published runs to about 4 MB of text, some four thousand positions, so this
# leaves roughly fiftyfold headroom over the largest book anyone has written.
MAX_PUBLICATION_POSITIONS = 4 * 50 * 1024 * 1024 // POSITION_LENGTH


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
