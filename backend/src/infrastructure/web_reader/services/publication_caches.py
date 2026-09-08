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

    **This only works because the API is one process.** Eviction is a method
    call on objects held in memory, so it reaches the caches in *this*
    interpreter and no other. ``Dockerfile`` runs ``uvicorn src.main:app`` with
    no ``--workers``, and the upload that replaces an EPUB is served by the same
    process that holds the caches, so today every cache that could go stale is
    told. Give uvicorn a second worker and that stops being true: a book
    replaced through worker A would go on being served from worker B's parse
    until its LRU happened to drop it, with no error anywhere to say so.

    Adding workers therefore means replacing this, not adding to it -- with a
    shared cache (Redis), or with a key that changes when the bytes do (a
    content hash rather than the filename, which is what makes an eviction
    unnecessary at all). Neither is worth building for a deployment that has one
    process; both are a day's work when it stops having one. See ADR-0004,
    Amendment 3.
    """

    def __init__(self, caches: Sequence[PublicationCacheProtocol]) -> None:
        self.caches = tuple(caches)

    def evict(self, ebook_file: str) -> None:
        """Drop everything cached for ``ebook_file``, everywhere."""
        for cache in self.caches:
            cache.evict(ebook_file)
