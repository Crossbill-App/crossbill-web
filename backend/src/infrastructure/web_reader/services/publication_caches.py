"""Every cache keyed on a book's EPUB filename, told about a replacement at once."""

from collections.abc import Sequence

from src.application.web_reader.protocols.publication_cache import PublicationCacheProtocol


class PublicationCaches:
    """Fans one eviction out to every cache that keys on ``Book.ebook_file``.

    Two of them exist now -- the parsed publications the anchor service holds
    and the position indices beside them -- and both go stale for the same
    reason at the same moment: ``Book.set_file`` reuses the filename, so
    replacing a book's EPUB changes the bytes behind a key both caches already
    hold (ADR-0004 §4).

    Implements ``PublicationCacheProtocol`` itself, so the upload path keeps
    depending on one thing and keeps having one line to get wrong, however many
    caches grow behind it.
    """

    def __init__(self, caches: Sequence[PublicationCacheProtocol]) -> None:
        self.caches = tuple(caches)

    def evict(self, ebook_file: str) -> None:
        """Drop everything cached for ``ebook_file``, everywhere."""
        for cache in self.caches:
            cache.evict(ebook_file)
