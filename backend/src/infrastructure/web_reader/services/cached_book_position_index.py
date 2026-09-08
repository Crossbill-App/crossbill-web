"""A book's position index, kept between requests so a page turn need not rebuild it."""

from __future__ import annotations

import logging
from collections import OrderedDict

from src.application.library.protocols.file_repository import FileRepositoryProtocol
from src.application.library.protocols.position_index_service import PositionIndexServiceProtocol
from src.domain.common.value_objects.position_index import PositionIndex

logger = logging.getLogger(__name__)

# How many books' indices to hold at once. An index is a dict of every element
# in a book keyed by its xpath, so this trades resident memory for a whole-EPUB
# parse -- the same bargain, and the same size, as the parsed publications the
# anchor service holds beside it (ADR-0004 §4).
POSITION_INDEX_CACHE_SIZE = 4


class CachedBookPositionIndex:
    """Builds position indices on demand and remembers them per ``ebook_file``.

    Implements ``BookPositionIndexProtocol`` and ``PublicationCacheProtocol``.

    The KOReader upload path builds an index once per sync and throws it away,
    which is why ``EpubPositionIndexService`` has no cache of its own. The web
    reader asks the same book the same question every few seconds, and building
    the index means reading and parsing the entire EPUB, so the answer is kept.

    A singleton, like the anchor service, because a cache that does not outlive
    the request is not a cache. Two concurrent misses for the same book build it
    twice and the later one wins, which costs a parse and nothing else.

    Process-local, and correct only while the API is one process -- see
    ``PublicationCaches``, which is what the upload path evicts through and
    where that constraint is written down.
    """

    def __init__(
        self,
        file_repository: FileRepositoryProtocol,
        position_index_service: PositionIndexServiceProtocol,
    ) -> None:
        self.file_repository = file_repository
        self.position_index_service = position_index_service
        self._indices: OrderedDict[str, PositionIndex] = OrderedDict()

    async def position_index_for(self, ebook_file: str) -> PositionIndex | None:
        """Return the book's index, building it on a miss.

        ``None`` when the store holds no such file, or the file cannot be parsed
        into one. A caller that cannot place its xpointer in document order
        still holds the canonical xpointer, so this is an unknown rather than a
        failure -- and a failure is not cached, so a file that arrives late is
        picked up by the next request.
        """
        cached = self._indices.get(ebook_file)
        if cached is not None:
            self._indices.move_to_end(ebook_file)
            return cached

        content = await self.file_repository.get_epub(ebook_file)
        if content is None:
            return None
        try:
            index = self.position_index_service.build_position_index(content)
        except Exception:
            logger.warning("Cannot build a position index for %s", ebook_file, exc_info=True)
            return None

        self._indices[ebook_file] = index
        if len(self._indices) > POSITION_INDEX_CACHE_SIZE:
            self._indices.popitem(last=False)
        return index

    def evict(self, ebook_file: str) -> None:
        """Drop any index cached for ``ebook_file``.

        The key is a filename that is reused when a book's EPUB is replaced, so
        whoever writes those bytes has to say so -- see
        ``PublicationCacheProtocol``.
        """
        if self._indices.pop(ebook_file, None) is not None:
            logger.debug("Evicted position index for %s", ebook_file)
