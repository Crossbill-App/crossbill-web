"""Read model for the grouped semantic-search response.

Search hits are hydrated here rather than through ``hydration.hydrate_hits``,
which resolves the *embedding input*: text truncated at
``MAX_EMBEDDABLE_CHARS`` and lossily concatenated, so a note cannot render its
title as a title. These views read each source module's own columns instead.

Every view carries its ``score`` -- cosine similarity on one scale for all three
types -- so a client is free to merge the groups back into one ranked list.

Ids are chosen for navigation. A digest carries both ``id`` (the indexed unit)
and ``chapter_id`` (what the chapter view opens on), and a note carries every
book it links to rather than one ``book_id``, because a note genuinely has no
single book.

These are view DTOs, not domain entities: they exist to be rendered and must
never be fed back into a command. See ``docs/adr/0001-read-models-and-query-services.md``.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from src.application.semantic.queries.semantic_search import SemanticSearchHit


@dataclass(frozen=True)
class BookRef:
    """A book as a search result names it."""

    id: int
    title: str


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
    datetime: str


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
