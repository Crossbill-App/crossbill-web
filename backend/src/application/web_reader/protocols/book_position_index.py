"""Port for turning a book's xpointers into ``Position`` values, cheaply enough to repeat."""

from typing import Protocol

from src.domain.common.value_objects.position_index import PositionIndex


class BookPositionIndexProtocol(Protocol):
    """A book's position index, held between requests.

    ``PositionIndexServiceProtocol`` builds an index by parsing a whole EPUB,
    which the KOReader upload path pays once per sync. The web reader asks the
    same question every time a page is turned, so it needs the answer kept: this
    port is the cached form, keyed by ``Book.ebook_file`` exactly as the parsed
    publications behind ``PositionAnchorServiceProtocol`` are (ADR-0004 §4).

    That key is reused when a book's EPUB is replaced, so implementations also
    implement ``PublicationCacheProtocol`` and are evicted on that path.
    """

    async def position_index_for(self, ebook_file: str) -> PositionIndex | None:
        """Return the book's index, building it on a miss.

        ``None`` when the store holds no such file or it cannot be parsed:
        an unresolvable position is a position that is simply unknown, not a
        failed request, and every caller of this already has a canonical
        xpointer in hand.
        """
        ...
