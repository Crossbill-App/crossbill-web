"""The rule that puts a document position in a chapter.

Ranges are written the way ``parse_toc`` builds them: each chapter ends where
the next table-of-contents entry begins, and the last one does not end.
"""

from datetime import UTC, datetime

from src.domain.common.value_objects.ids import BookId, ChapterId
from src.domain.common.value_objects.position import Position
from src.domain.library.entities.chapter import Chapter
from src.domain.library.services.chapter_position_resolver import ChapterPositionResolver


def chapter(
    id: int,
    name: str,
    start: int | None,
    end: int | None,
    chapter_number: int | None = None,
) -> Chapter:
    return Chapter.create_with_id(
        id=ChapterId(id),
        book_id=BookId(1),
        name=name,
        created_at=datetime.now(UTC),
        chapter_number=chapter_number,
        start_position=Position(index=start) if start is not None else None,
        end_position=Position(index=end) if end is not None else None,
    )


ONE = chapter(1, "One", start=1, end=10)
TWO = chapter(2, "Two", start=10, end=20)
THREE = chapter(3, "Three", start=20, end=None)
BOOK = [ONE, TWO, THREE]

resolver = ChapterPositionResolver()


def test_a_chapters_own_start_belongs_to_it_and_its_end_to_the_next() -> None:
    assert resolver.chapter_at(BOOK, Position(index=10)) is TWO
    assert resolver.chapter_at(BOOK, Position(index=9)) is ONE


def test_a_position_in_a_gap_between_ranges_belongs_to_no_chapter() -> None:
    # Ranges only meet because each end is the next entry's start. Where they do
    # not -- a chapter positioned against an EPUB since replaced -- the end stays
    # exclusive rather than swallowing the ground after it.
    gapped = [chapter(1, "One", start=1, end=10), chapter(3, "Three", start=20, end=None)]

    assert resolver.chapter_at(gapped, Position(index=10)) is None
    assert resolver.chapter_at(gapped, Position(index=19)) is None
    assert resolver.chapter_at(gapped, Position(index=20)) is gapped[1]


def test_a_position_before_every_chapter_belongs_to_none() -> None:
    assert resolver.chapter_at(BOOK, Position(index=0)) is None


def test_char_index_separates_positions_inside_the_same_element() -> None:
    boundary = [chapter(1, "One", start=1, end=None), chapter(2, "Two", start=10, end=None)]
    boundary[1].start_position = Position(index=10, char_index=40)

    assert resolver.chapter_at(boundary, Position(index=10, char_index=39)) is boundary[0]
    assert resolver.chapter_at(boundary, Position(index=10, char_index=40)) is boundary[1]


def test_a_chapter_without_a_start_is_never_placed() -> None:
    unplaced = chapter(4, "Unplaced", start=None, end=None)

    assert resolver.chapter_at([unplaced], Position(index=5)) is None
    assert resolver.chapter_at([unplaced, *BOOK], Position(index=5)) is ONE


def test_nesting_picks_the_innermost_chapter() -> None:
    # What a table of contents out of reading order leaves behind: a part that
    # really does span its children rather than ending where the first one starts.
    part = chapter(10, "Part I", start=1, end=100)
    inner = chapter(11, "Chapter 1", start=1, end=50)
    later = chapter(12, "Chapter 2", start=50, end=100)

    assert resolver.chapter_at([part, inner, later], Position(index=20)) is inner
    assert resolver.chapter_at([inner, part, later], Position(index=20)) is inner
    assert resolver.chapter_at([part, inner, later], Position(index=60)) is later
