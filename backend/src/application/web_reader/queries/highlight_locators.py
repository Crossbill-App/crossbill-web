"""Read model for the Readium locators stored on a book's highlights.

The highlights themselves belong to ``reading``; what this view answers is the
web reader's own question -- where in the EPUB do I draw this. R4.2's ingest
already derived and stored the answer, so nothing here parses a book: the read
serves a stored locator or says why there is none.

Whether a stored locator still applies is decided by comparing
``highlights.locator_source_hash`` against ``book_publications.content_hash``,
both written by ``epub_content_hash`` (ADR-0004, *Amendment 6*).
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from src.application.web_reader.anchors import Locator
from src.domain.common.value_objects.ids import BookId, HighlightId, UserId


class LocatorUnavailable(StrEnum):
    """Why a highlight has no locator, in terms a client can act on.

    Attributes:
        NO_EBOOK: The book has no stored publication. It cannot be opened in the
            reader at all, so no highlight in it can be placed, and nothing is
            wrong with any of them.
        UNRESOLVED: This one highlight has no locator against the book's current
            EPUB -- none was ever derived, or the stored one belongs to a file
            the book no longer holds.
    """

    NO_EBOOK = "no_ebook"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class HighlightLocatorView:
    """Where one highlight is in the EPUB, or why that cannot be said.

    Exactly one of ``locator`` and ``unavailable`` is set. The locator is in
    *container* coordinates -- a router points its href at the serving URL.
    """

    highlight_id: int
    locator: Locator | None = None
    unavailable: LocatorUnavailable | None = None


@dataclass(frozen=True)
class StoredHighlightLocator:
    """One highlight's locator columns, as an ingest left them.

    ``source_hash`` names the EPUB the locator was derived from, and is ``None``
    where no ingest has ever run against the row.
    """

    highlight_id: int
    locator: Locator | None
    source_hash: str | None


@dataclass(frozen=True)
class BookHighlightLocators:
    """One book's live highlights in id order, beside the digest they are judged against.

    ``publication_hash`` is ``None`` when the book has no publication row --
    distinct from the port answering ``None``, which means no such book.
    """

    publication_hash: str | None
    highlights: tuple[StoredHighlightLocator, ...]


@dataclass(frozen=True)
class HighlightLocatorInBook:
    """One highlight's stored locator, beside the digest it is judged against.

    ``publication_hash`` is ``None`` when the book has no publication row --
    distinct from the port answering ``None``, which means no such highlight.
    """

    publication_hash: str | None
    highlight: StoredHighlightLocator


class HighlightLocatorQueryProtocol(Protocol):
    """Port reading the locator columns and the publication digest beside them."""

    async def locators_for_book(
        self, book_id: BookId, user_id: UserId
    ) -> BookHighlightLocators | None:
        """Return the book's stored locators, or ``None`` if the user has no such book."""
        ...

    async def locator_for_highlight(
        self, highlight_id: HighlightId, user_id: UserId
    ) -> HighlightLocatorInBook | None:
        """Return one highlight's stored locator, or ``None`` if the user has no live one."""
        ...


def locator_view(
    stored: StoredHighlightLocator, publication_hash: str | None
) -> HighlightLocatorView:
    """Serve a stored locator only while it names the book's current EPUB.

    A locator derived from a file the book no longer holds is withheld rather
    than served or recomputed: it would place the highlight confidently, in the
    wrong edition.
    """
    if publication_hash is None:
        return HighlightLocatorView(
            highlight_id=stored.highlight_id, unavailable=LocatorUnavailable.NO_EBOOK
        )
    if stored.locator is None or stored.source_hash != publication_hash:
        return HighlightLocatorView(
            highlight_id=stored.highlight_id, unavailable=LocatorUnavailable.UNRESOLVED
        )
    return HighlightLocatorView(highlight_id=stored.highlight_id, locator=stored.locator)
