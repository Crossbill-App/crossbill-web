"""Read model for the Readium locators a book's highlights derive to (M3.1, #745).

The highlights themselves are ``reading``'s -- this module never renders one.
What it holds is the web reader's own answer to *where in the EPUB is this
highlight*, which ADR-0004 §2 makes a derived thing: computed from the stored
``XPointRange`` and the EPUB file, never stored, never authoritative.

Two DTO families, and the split is the point. :class:`HighlightAnchor` is the
*input* -- the canonical position and the text that was stored beside it, which
is all the derivation needs from the ``reading`` tables.
:class:`DerivedHighlightLocator` is the *output*, and it is deliberately a
two-field answer rather than an optional locator: a highlight that cannot be
placed says so with a reason a client can branch on (ADR-0004 §5), because
"there is no locator" and "the EPUB was replaced under this highlight" are not
the same news.
"""

from collections.abc import Collection
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from src.application.web_reader.anchors import Locator
from src.domain.common.value_objects.ids import BookId, HighlightId, UserId
from src.domain.common.value_objects.xpoint import XPointRange


class LocatorUnavailable(StrEnum):
    """Why a highlight has no locator, in terms a client can act on.

    The first two are about the *book* and the last three about the *highlight*,
    and keeping that line sharp is the point of the enum. ``NO_EBOOK`` says no
    highlight in this book can be placed and nothing is wrong with any of them;
    ``UNRESOLVED`` says this one highlight's position is lost. Collapsing a
    missing file into the latter would tell a reader their positions were
    destroyed when what is actually gone is the file.

    Attributes:
        NO_EBOOK: There is no readable EPUB to derive against -- the book has
            none stored, the file is not in the store any more, or what is there
            does not parse. One reason for all three because a client can do
            nothing different about them: the book cannot be opened in the
            reader at all, and no highlight in it can be placed. Which of the
            three it was is in the logs, where the difference between normal
            state and data loss actually matters.
        NOT_PLACEABLE: The highlight carries no xpointer range. Highlights
            synced by older plugin versions, and any typed in by hand, have text
            and no position -- they are real highlights that were never anywhere
            in particular.
        UNRESOLVED: The conversion failed for this highlight against an EPUB
            that read and parsed perfectly well: its stored xpointer names a
            place this edition does not have.
        TEXT_MISMATCH: The conversion succeeded and landed on different text.
            The dangerous case ADR-0004 §5 exists for -- a confident locator
            pointing at the wrong paragraph -- caught by comparing what the
            derived anchor covers against the text stored with the highlight.
        GONE: The highlight was deleted between the two reads a response is
            built from -- the view that listed it, and the anchor lookup that
            was to place it. Rare and harmless, but it still has to be *said*:
            the schema promises a reason wherever there is no locator, and a
            client that trusts that promise must not meet a null pair.
    """

    NO_EBOOK = "no_ebook"
    NOT_PLACEABLE = "not_placeable"
    UNRESOLVED = "unresolved"
    TEXT_MISMATCH = "text_mismatch"
    GONE = "gone"


@dataclass(frozen=True)
class DerivedHighlightLocator:
    """Where one highlight is in the EPUB, or why that could not be answered.

    Exactly one of the two fields is set. A verified locator carries no reason;
    a reason carries no locator, because a locator that failed verification is
    the thing this read model exists to withhold.

    Attributes:
        highlight_id: The highlight this answers for.
        locator: The verified Readium locator, in *container* coordinates --
            the href is the path inside the EPUB, and a router points it at the
            URL that serves the resource.
        unavailable: Why there is no locator.
    """

    highlight_id: int
    locator: Locator | None = None
    unavailable: LocatorUnavailable | None = None


@dataclass(frozen=True)
class HighlightAnchor:
    """One highlight's canonical position and the text stored with it.

    The text is not for rendering: it is the evidence the derived locator is
    verified against (ADR-0004 §5), and it never reaches a response.

    Attributes:
        highlight_id: The highlight's id.
        xpoints: The stored range, or ``None`` for a highlight that was never
            placed.
        text: The highlight text as stored.
    """

    highlight_id: int
    xpoints: XPointRange | None
    text: str


@dataclass(frozen=True)
class BookHighlightAnchors:
    """Everything the derivation needs about one book's highlights.

    Carries the book's ``ebook_file`` alongside the rows because they are
    converted together, against one parse of that one file. A single-highlight
    lookup answers with this same shape holding one row, so there is one
    derivation and not two.

    Attributes:
        book_id: The book these highlights belong to. Not needed to *convert*
            anything -- the conversion works off the xpointers and the file --
            but a conversion that fails is reported with the book it failed in
            (M3.4, #748), and a single-highlight lookup would otherwise have no
            way to say which book that was.
        ebook_file: The stored EPUB's filename, or ``None`` if the book has no
            EPUB.
        highlights: The highlights to place.
    """

    book_id: int
    ebook_file: str | None
    highlights: tuple[HighlightAnchor, ...]


class HighlightAnchorQueryProtocol(Protocol):
    """Port reading the canonical positions the web reader derives locators from.

    Deliberately narrow: it selects the xpointer columns and the highlight text
    and nothing else. The rendered highlight -- label, tags, flashcards --
    belongs to ``reading``'s own read models, and duplicating it here would make
    two places to keep a highlight's shape right.
    """

    async def anchors_for_book(
        self,
        book_id: BookId,
        user_id: UserId,
        highlight_ids: Collection[int] | None = None,
    ) -> BookHighlightAnchors | None:
        """Return the book's live highlights, or ``None`` if the user has no such book.

        ``highlight_ids`` narrows the set to the highlights a caller is actually
        going to render; ``None`` means the whole book, which is what a reader
        drawing every decoration wants.
        """
        ...

    async def anchor_for_highlight(
        self, highlight_id: HighlightId, user_id: UserId
    ) -> BookHighlightAnchors | None:
        """Return one live highlight, or ``None`` if the user has no such highlight."""
        ...
