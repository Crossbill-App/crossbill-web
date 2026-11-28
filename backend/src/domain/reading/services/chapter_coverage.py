"""Chapter Coverage and Read Chapter, measured in characters of the book."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

from src.domain.common.value_objects.ids import ChapterId

READING_SPEED_CHARACTERS_PER_SECOND = 60
READ_CHAPTER_COVERAGE = 0.8


class ChapterReadState(StrEnum):
    READ = "read"
    NOT_READ = "not_read"
    UNMEASURABLE = "unmeasurable"


@dataclass(frozen=True)
class CharacterRange:
    """Characters ``[start, end)`` counted from the start of the book."""

    start: int
    end: int

    @property
    def length(self) -> int:
        return max(0, self.end - self.start)


@dataclass(frozen=True)
class PageViewSpan:
    """The slice of a Page View that coverage needs: its characters and time on screen."""

    characters: CharacterRange
    duration: timedelta

    @property
    def stayed_long_enough_to_read(self) -> bool:
        seconds_needed = self.characters.length / READING_SPEED_CHARACTERS_PER_SECOND
        return self.duration.total_seconds() >= seconds_needed


@dataclass(frozen=True)
class ChapterStart:
    """Where a chapter starts, ``None`` when it has no place in the text."""

    chapter_id: ChapterId
    start_offset: int | None


@dataclass(frozen=True)
class ChapterCoverage:
    """The share of a chapter's own text that was read, ``None`` when unmeasurable."""

    chapter_id: ChapterId
    coverage: float | None

    @property
    def read_state(self) -> ChapterReadState:
        if self.coverage is None:
            return ChapterReadState.UNMEASURABLE
        if self.coverage >= READ_CHAPTER_COVERAGE:
            return ChapterReadState.READ
        return ChapterReadState.NOT_READ


def measure_chapter_coverage(
    chapters_in_reading_order: Sequence[ChapterStart],
    total_characters: int | None,
    page_view_spans: Sequence[PageViewSpan],
) -> tuple[ChapterCoverage, ...]:
    """Measure every chapter's coverage from the Page Views of all its book's sessions.

    A chapter's own text runs to the next chapter that has a start, or to the
    end of the book.
    """
    read_ranges = _union(
        view.characters for view in page_view_spans if view.stayed_long_enough_to_read
    )
    return tuple(
        ChapterCoverage(chapter.chapter_id, _coverage(own_text, read_ranges))
        for chapter, own_text in _own_text_ranges(chapters_in_reading_order, total_characters)
    )


def _own_text_ranges(
    chapters: Sequence[ChapterStart], total_characters: int | None
) -> list[tuple[ChapterStart, CharacterRange | None]]:
    end = total_characters
    ranges: list[CharacterRange | None] = []
    for chapter in reversed(chapters):
        start = chapter.start_offset
        ranges.append(None if start is None or end is None else CharacterRange(start, end))
        if start is not None:
            end = start
    return list(zip(chapters, reversed(ranges), strict=True))


def _union(ranges: Iterable[CharacterRange]) -> list[CharacterRange]:
    merged: list[CharacterRange] = []
    for current in sorted(ranges, key=lambda r: r.start):
        if current.length == 0:
            continue
        if merged and current.start <= merged[-1].end:
            merged[-1] = CharacterRange(merged[-1].start, max(merged[-1].end, current.end))
        else:
            merged.append(current)
    return merged


def _coverage(
    own_text: CharacterRange | None, read_ranges: Sequence[CharacterRange]
) -> float | None:
    if own_text is None or own_text.length == 0:
        return None
    characters_read = sum(
        max(0, min(own_text.end, span.end) - max(own_text.start, span.start))
        for span in read_ranges
    )
    return characters_read / own_text.length
