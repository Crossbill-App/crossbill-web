"""Ranking rules applied to a scan's candidates before they are hydrated.

Pure functions over ``SemanticSearchHit``: no I/O, no session, no ORM. They sit
in the application layer because they are policy, not SQL -- the SQLite test
path and the pgvector path hand back the same hits and get the same page out.

Every number here was measured in the semantic-lab research repo (experiments
003 to 006) against the owner's library and two judges' relevance labels. They
are tuned to one embedding model (``bge-m3``) and one corpus; a model swap
invalidates them and means re-running the lab, not nudging a constant.
"""

from collections.abc import Mapping, Sequence

from src.application.semantic.content_type import ContentType
from src.application.semantic.queries.semantic_search import SemanticSearchHit

#: Cosine floor below which a free-text match is not worth showing.
#:
#: Nearest-neighbour search always answers with its top ``k``, so a query with
#: no real match still comes back with the least-bad rows. 0.45 empties all four
#: nonsense queries in the lab's evalset while losing no judged-relevant result:
#: the best nonsense score is 0.435, the worst real query's top score 0.529. The
#: gap is wide enough that no floor between 0.35 and 0.55 changes precision, so
#: this sits in the middle of a plateau rather than on an edge.
SEARCH_SCORE_FLOOR = 0.45

#: Cosine floor for related content, higher than search's because the bar is.
#:
#: A free-text query is something the reader asked for; a related strip is
#: unasked-for, so a weak row costs more than a missing one. 0.60 sits between
#: the two judges' 0.70-precision crossings, and removes nothing from a merged
#: page once the cap below has fired.
RELATED_SCORE_FLOOR = 0.60

#: How many candidates to rank per requested row before the cap picks a page.
#:
#: The cap can only spread a page across books if it has more than ``limit``
#: rows to choose from; four times is what the lab's diversity gains were
#: measured at.
CANDIDATE_FACTOR = 4

#: A candidate is evidence of a genuinely cross-book neighbourhood at or above
#: this score. Below it, "another book also mentions this" is noise.
CROSS_BOOK_SCORE = 0.62

#: How many such candidates the pooled ranking needs before the cap fires.
#:
#: The cap is gated rather than unconditional because an unconditional one drops
#: related precision@10 from 0.73 to 0.29 on the lab's seven "isolated" anchors
#: -- technical books and novels, where the only real neighbours are in the same
#: book and capping them backfills noise. At 10 the gate matched 21 of the
#: owner's 28 side-by-side choices, always capping the 15 it should and never
#: the 13 it should not.
CROSS_BOOK_GATE = 10

#: Results per book once the cap fires, per content type.
MAX_PER_BOOK = 2


def above_floor(hits: Sequence[SemanticSearchHit], floor: float) -> list[SemanticSearchHit]:
    """Drop hits scoring below ``floor``, keeping the rest in order.

    Applied *after* a page is chosen, never before: a short page is the point.
    Filtering first and slicing after would backfill the dropped rows with the
    next-best ones, which are by construction worse than what was just rejected.
    """
    return [hit for hit in hits if hit.score >= floor]


def is_cross_book(hit: SemanticSearchHit, anchor_book_id: int | None) -> bool:
    """Whether a candidate comes from somewhere other than the anchor's book.

    A hit with no book is always cross-book. ``embeddings.book_id`` is NULL for
    a note linked to zero or several books (ADR-0002, *Storage*), and such a
    note is exactly the kind of connection across the library that the gate
    below exists to detect -- counting it as same-book would hide it.
    """
    return hit.book_id is None or hit.book_id != anchor_book_id


def has_cross_book_neighbourhood(
    pooled: Sequence[SemanticSearchHit], anchor_book_id: int | None
) -> bool:
    """Whether the anchor's neighbourhood reaches beyond its own book.

    Counted over the *pooled* candidates of every content type, not per type: it
    is one question about the anchor, and a note-poor library would answer it
    differently for each type otherwise.
    """
    return (
        sum(
            1
            for hit in pooled
            if hit.score >= CROSS_BOOK_SCORE and is_cross_book(hit, anchor_book_id)
        )
        >= CROSS_BOOK_GATE
    )


def cap_per_book(hits: Sequence[SemanticSearchHit], limit: int) -> list[SemanticSearchHit]:
    """Take the best ``limit`` hits, at most ``MAX_PER_BOOK`` from any one book.

    Walks the ranked list in order, skipping a hit whose book is already full,
    so the page stays sorted by score and simply reaches further down for its
    later rows. Bookless hits are never skipped: each is its own bucket, since
    "one book crowding the page" is not something a note linked to zero or
    several books can do.
    """
    kept: list[SemanticSearchHit] = []
    taken: dict[int, int] = {}
    for hit in hits:
        if hit.book_id is not None:
            if taken.get(hit.book_id, 0) >= MAX_PER_BOOK:
                continue
            taken[hit.book_id] = taken.get(hit.book_id, 0) + 1
        kept.append(hit)
        if len(kept) == limit:
            break
    return kept


def related_page(
    candidates: Mapping[ContentType, Sequence[SemanticSearchHit]],
    *,
    anchor_book_id: int | None,
    limit: int,
) -> dict[ContentType, list[SemanticSearchHit]]:
    """Turn over-fetched candidates into the page ``/related`` answers with.

    Gate first over everything ranked, then cap and floor each type on its own.
    The gate is one decision for the whole page -- capping highlights but not
    digests would make the strip's diversity depend on which type the reader
    happened to be looking at.
    """
    pooled = [hit for hits in candidates.values() for hit in hits]
    spread = has_cross_book_neighbourhood(pooled, anchor_book_id)
    return {
        content_type: above_floor(
            cap_per_book(hits, limit) if spread else list(hits[:limit]),
            RELATED_SCORE_FLOOR,
        )
        for content_type, hits in candidates.items()
    }
