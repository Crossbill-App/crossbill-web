"""Read model for the grouped semantic-search response.

Both reads that rank the index -- /search and /related -- hydrate through here.
These views read each source module's own display columns rather than the
*embedding input*, which is text truncated at ``MAX_EMBEDDABLE_CHARS`` and
lossily concatenated, and so cannot render a note's title as a title.

Every view carries its ``score`` -- cosine similarity on one scale for all three
types -- so a client is free to merge the groups back into one ranked list.

Ids are chosen for navigation. A digest carries both ``id`` (the indexed unit)
and ``chapter_id`` (what the chapter view opens on), and a note carries every
book it links to rather than one ``book_id``, because a note genuinely has no
single book.

These are view DTOs, not domain entities: they exist to be rendered and must
never be fed back into a command. See ``docs/adr/0001-read-models-and-query-services.md``.
"""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime as dt
from typing import Protocol

from src.application.semantic.content_type import ContentType
from src.application.semantic.queries.semantic_search import SemanticSearchHit


@dataclass(frozen=True)
class BookRef:
    """A book as a search result names it."""

    id: int
    title: str
    cover_file: str | None
    cover_blurhash: str | None


@dataclass(frozen=True)
class HighlightSearchView:
    """A matched highlight, with what a highlight list row shows."""

    score: float
    id: int
    book_id: int
    book_title: str
    chapter_id: int | None
    chapter_name: str | None
    chapter_number: int | None
    text: str
    page: int | None
    datetime: dt
    cover_file: str | None
    cover_blurhash: str | None


@dataclass(frozen=True)
class NoteSearchView:
    """A matched note. ``books`` may be empty -- a note need not link to any."""

    score: float
    id: int
    books: tuple[BookRef, ...]
    title: str
    body: str
    kind: str | None


@dataclass(frozen=True)
class DigestSearchView:
    """A matched chapter digest.

    ``id`` is the digest's own id -- the unit that was embedded, and what the
    score belongs to. ``chapter_id`` is what a caller navigates to.
    """

    score: float
    id: int
    book_id: int
    book_title: str
    chapter_id: int
    chapter_name: str
    chapter_number: int | None
    summary: str
    keypoints: tuple[str, ...]
    cover_file: str | None
    cover_blurhash: str | None


@dataclass(frozen=True)
class SemanticSearchResultsView:
    """One search's matches, grouped by content type, each group most similar first."""

    highlights: tuple[HighlightSearchView, ...]
    notes: tuple[NoteSearchView, ...]
    digests: tuple[DigestSearchView, ...]


class SearchHydrationQueryProtocol(Protocol):
    """Port for resolving hits into renderable items, one method per content type.

    Each method preserves the ranking order of ``hits`` and drops any hit whose
    source row does not resolve -- which is what makes "deleted content never
    surfaces" true (ADR-0002's consistency model, rule 2). ``user_id`` is
    enforced again here rather than trusted from the scan.
    """

    async def highlights(
        self, hits: Sequence[SemanticSearchHit], user_id: int
    ) -> tuple[HighlightSearchView, ...]:
        """Resolve highlight hits, dropping any that are gone or soft-deleted."""
        ...

    async def notes(
        self, hits: Sequence[SemanticSearchHit], user_id: int
    ) -> tuple[NoteSearchView, ...]:
        """Resolve note hits together with the books each links to."""
        ...

    async def digests(
        self, hits: Sequence[SemanticSearchHit], user_id: int
    ) -> tuple[DigestSearchView, ...]:
        """Resolve digest hits, carrying their chapter and book context."""
        ...


async def hydrate_by_content_type(
    page: Mapping[ContentType, Sequence[SemanticSearchHit]],
    hydration: SearchHydrationQueryProtocol,
    user_id: int,
) -> SemanticSearchResultsView:
    """Resolve an already-chosen page, one hydration query per content type.

    Both ranked reads end here. ``/related`` calls it directly because it cannot
    hydrate a type until every type has been ranked -- its per-book cap is gated
    on the whole neighbourhood, not on one group at a time.
    """
    return SemanticSearchResultsView(
        highlights=await hydration.highlights(page[ContentType.HIGHLIGHT], user_id),
        notes=await hydration.notes(page[ContentType.NOTE], user_id),
        digests=await hydration.digests(page[ContentType.DIGEST], user_id),
    )


async def group_by_content_type(
    scan: Callable[[ContentType], Awaitable[Sequence[SemanticSearchHit]]],
    hydration: SearchHydrationQueryProtocol,
    user_id: int,
) -> SemanticSearchResultsView:
    """Scan the index once per content type and hydrate each group on its own.

    One scan per type rather than one combined scan: a book with thousands of
    highlights would otherwise fill a single ranked page and the digests would
    never appear.
    """
    return await hydrate_by_content_type(
        {
            ContentType.HIGHLIGHT: await scan(ContentType.HIGHLIGHT),
            ContentType.NOTE: await scan(ContentType.NOTE),
            ContentType.DIGEST: await scan(ContentType.DIGEST),
        },
        hydration,
        user_id,
    )
