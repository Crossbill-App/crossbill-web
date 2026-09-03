"""Unit tests for the pure ranking rules behind /search and /related.

These functions are where the lab's measured constants live, and they branch on
inputs an API test can only reach indirectly -- a score a hair under a
threshold, a candidate with no book at all. No mocks: hits are plain frozen
dataclasses.
"""

from src.application.semantic.content_type import ContentType
from src.application.semantic.queries.ranking import (
    CROSS_BOOK_GATE,
    CROSS_BOOK_SCORE,
    MAX_PER_BOOK,
    RELATED_SCORE_FLOOR,
    above_floor,
    cap_per_book,
    has_cross_book_neighbourhood,
    is_cross_book,
    related_page,
)
from src.application.semantic.queries.semantic_search import SemanticSearchHit

ANCHOR_BOOK = 1
OTHER_BOOK = 2


def hit(
    content_id: int,
    *,
    book_id: int | None = ANCHOR_BOOK,
    score: float = 1.0,
    content_type: ContentType = ContentType.HIGHLIGHT,
) -> SemanticSearchHit:
    return SemanticSearchHit(
        content_type=content_type, content_id=content_id, book_id=book_id, score=score
    )


def ids(hits: list[SemanticSearchHit]) -> list[int]:
    return [hit.content_id for hit in hits]


class TestAboveFloor:
    def test_keeps_a_hit_exactly_at_the_floor(self) -> None:
        """The floor is a minimum, not a strict one -- a hit at it is a match."""
        assert ids(above_floor([hit(1, score=0.6)], 0.6)) == [1]

    def test_drops_what_is_below_and_keeps_the_order_of_the_rest(self) -> None:
        hits = [hit(1, score=0.9), hit(2, score=0.5), hit(3, score=0.7)]

        assert ids(above_floor(hits, 0.6)) == [1, 3]


class TestIsCrossBook:
    def test_the_anchors_own_book_is_not_cross_book(self) -> None:
        assert not is_cross_book(hit(1, book_id=ANCHOR_BOOK), ANCHOR_BOOK)

    def test_another_book_is(self) -> None:
        assert is_cross_book(hit(1, book_id=OTHER_BOOK), ANCHOR_BOOK)

    def test_a_bookless_hit_is_cross_book_even_against_a_bookless_anchor(self) -> None:
        """Two notes each linked to several books are a connection across the library.

        Both rows carry NULL, and comparing the columns would call them the same
        book -- the one case where equality is the wrong question.
        """
        assert is_cross_book(hit(1, book_id=None), None)

    def test_a_bookless_anchor_is_not_the_same_book_as_everything(self) -> None:
        assert is_cross_book(hit(1, book_id=OTHER_BOOK), None)


class TestHasCrossBookNeighbourhood:
    def test_fires_at_the_gate_count(self) -> None:
        pooled = [
            hit(i, book_id=OTHER_BOOK, score=CROSS_BOOK_SCORE) for i in range(CROSS_BOOK_GATE)
        ]

        assert has_cross_book_neighbourhood(pooled, ANCHOR_BOOK)

    def test_does_not_fire_one_candidate_short(self) -> None:
        pooled = [
            hit(i, book_id=OTHER_BOOK, score=CROSS_BOOK_SCORE) for i in range(CROSS_BOOK_GATE - 1)
        ]

        assert not has_cross_book_neighbourhood(pooled, ANCHOR_BOOK)

    def test_a_candidate_just_under_the_score_does_not_count(self) -> None:
        """Weak cross-book matches are the noise the gate exists to ignore.

        They sit above the page's own floor, so a gate that counted every
        cross-book candidate would fire on a library of loosely similar books.
        """
        pooled = [
            hit(i, book_id=OTHER_BOOK, score=CROSS_BOOK_SCORE - 0.01)
            for i in range(CROSS_BOOK_GATE)
        ]

        assert not has_cross_book_neighbourhood(pooled, ANCHOR_BOOK)

    def test_the_anchors_own_book_cannot_open_the_gate(self) -> None:
        pooled = [hit(i, score=1.0) for i in range(CROSS_BOOK_GATE * 2)]

        assert not has_cross_book_neighbourhood(pooled, ANCHOR_BOOK)


class TestCapPerBook:
    def test_reaches_past_a_full_book_for_its_later_rows(self) -> None:
        hits = [hit(1), hit(2), hit(3), hit(4, book_id=OTHER_BOOK)]

        assert ids(cap_per_book(hits, limit=3)) == [1, 2, 4]

    def test_stops_at_the_limit(self) -> None:
        hits = [hit(1), hit(2), hit(3, book_id=OTHER_BOOK), hit(4, book_id=OTHER_BOOK)]

        assert ids(cap_per_book(hits, limit=3)) == [1, 2, 3]

    def test_returns_a_short_page_rather_than_exceeding_the_cap(self) -> None:
        assert ids(cap_per_book([hit(1), hit(2), hit(3)], limit=3)) == [1, 2]

    def test_never_caps_bookless_hits(self) -> None:
        """A note linked to zero or several books is nobody's crowd.

        The cap holds back a book that would fill the page; a bookless row has
        no book to be held back on behalf of, so each is its own bucket.
        """
        hits = [hit(i, book_id=None) for i in range(1, MAX_PER_BOOK + 3)]

        assert ids(cap_per_book(hits, limit=10)) == [1, 2, 3, 4]


class TestRelatedPage:
    def test_takes_the_plain_top_of_each_type_when_the_gate_is_shut(self) -> None:
        candidates = {
            ContentType.HIGHLIGHT: [hit(i) for i in range(1, 6)],
            ContentType.NOTE: [],
            ContentType.DIGEST: [],
        }

        page = related_page(candidates, anchor_book_id=ANCHOR_BOOK, limit=3)

        assert ids(page[ContentType.HIGHLIGHT]) == [1, 2, 3]

    def test_pools_every_type_to_decide_whether_to_cap(self) -> None:
        """Half the evidence is in notes, and it still caps the highlights.

        Counting per type instead would make a strip's diversity depend on which
        type the reader happened to be looking at, and a note-poor library would
        never cap its notes at all.
        """
        half = CROSS_BOOK_GATE // 2
        candidates = {
            ContentType.HIGHLIGHT: [hit(i) for i in range(1, 6)]
            + [hit(10 + i, book_id=OTHER_BOOK) for i in range(half)],
            ContentType.NOTE: [
                hit(20 + i, book_id=OTHER_BOOK, content_type=ContentType.NOTE)
                for i in range(CROSS_BOOK_GATE - half)
            ],
            ContentType.DIGEST: [],
        }

        page = related_page(candidates, anchor_book_id=ANCHOR_BOOK, limit=3)

        assert ids(page[ContentType.HIGHLIGHT]) == [1, 2, 10]

    def test_floors_the_page_it_chose_instead_of_backfilling_under_it(self) -> None:
        """The row under the floor is dropped; the one behind it is not promoted.

        Filtering before the page was chosen would pull row 4 up into the gap,
        and row 4 is by construction worse than the row just rejected.
        """
        candidates = {
            ContentType.HIGHLIGHT: [
                hit(1, score=0.9),
                hit(2, score=RELATED_SCORE_FLOOR - 0.01),
                hit(3, score=0.7),
                hit(4, score=0.65),
            ],
            ContentType.NOTE: [],
            ContentType.DIGEST: [],
        }

        page = related_page(candidates, anchor_book_id=ANCHOR_BOOK, limit=3)

        assert ids(page[ContentType.HIGHLIGHT]) == [1, 3]
