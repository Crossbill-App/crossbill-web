"""Port for invalidating the parsed-publication cache when an EPUB changes."""

from typing import Protocol


class PublicationCacheProtocol(Protocol):
    """The eviction half of the anchor service's per-book EPUB cache.

    Deriving an anchor parses the book's EPUB, so the anchor service holds parsed
    publications keyed by ``Book.ebook_file``. That key is *stable across
    re-uploads* -- ``Book.set_file`` reuses the existing filename -- so replacing
    a book's EPUB changes the bytes behind a key the cache already holds.
    Whoever writes those bytes has to say so.

    Kept separate from ``PositionAnchorServiceProtocol`` so the upload path can
    depend on the one thing it needs, rather than on a conversion service it
    never calls. One adapter implements both.
    """

    def evict(self, ebook_file: str) -> None:
        """Drop any parsed publication cached for ``ebook_file``.

        A no-op when nothing is cached for that key.
        """
        ...
