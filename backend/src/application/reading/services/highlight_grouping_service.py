"""Domain service for grouping highlights by chapter."""

from collections import defaultdict
from dataclasses import dataclass
from typing import Generic, TypeVar

from src.domain.common.value_objects.position import Position
from src.domain.learning.entities.flashcard import Flashcard
from src.domain.library.entities.chapter import Chapter
from src.domain.reading.entities.highlight import Highlight

# Tags belong to the tagging module. Grouping only carries them through, so the
# tag type stays a parameter and reading keeps no dependency on tagging.
TagT = TypeVar("TagT")


@dataclass
class HighlightWithContext(Generic[TagT]):
    """Highlight with its associated context (chapter, tags, flashcards)."""

    highlight: Highlight
    chapter: Chapter | None
    tags: list[TagT]
    flashcards: list[Flashcard]


@dataclass
class ChapterWithHighlights(Generic[TagT]):
    """Chapter with its associated highlights."""

    chapter_id: int
    chapter_name: str | None
    chapter_number: int | None
    highlights: list[HighlightWithContext[TagT]]
    parent_id: int | None = None
    start_position: Position | None = None


class HighlightGroupingService:
    """Stateless domain service for grouping highlights by chapter."""

    @staticmethod
    def group_by_chapter(
        highlights_with_context: list[
            tuple[Highlight, Chapter | None, list[TagT], list[Flashcard]]
        ],
    ) -> list[ChapterWithHighlights[TagT]]:
        """
        Group highlights by chapter, sorted by chapter number.

        Args:
            highlights_with_context: List of tuples (highlight, chapter, tags, flashcards)

        Returns:
            List of ChapterWithHighlights, sorted by chapter_number
        """
        # Group by chapter_id
        grouped: dict[int | None, list[HighlightWithContext[TagT]]] = defaultdict(list)
        chapter_lookup: dict[int, Chapter] = {}

        for highlight, chapter, tags, flashcards in highlights_with_context:
            chapter_id = highlight.chapter_id.value if highlight.chapter_id else None

            # Store chapter for later lookup
            if chapter and chapter_id:
                chapter_lookup[chapter_id] = chapter

            grouped[chapter_id].append(
                HighlightWithContext(
                    highlight=highlight, chapter=chapter, tags=tags, flashcards=flashcards
                )
            )

        # Build results, sorted by chapter_number
        results: list[ChapterWithHighlights[TagT]] = []
        sorted_chapter_ids = sorted(
            [cid for cid in grouped if cid is not None],
            key=lambda cid: chapter_lookup[cid].chapter_number or 0,
        )

        for chapter_id in sorted_chapter_ids:
            chapter = chapter_lookup.get(chapter_id)
            results.append(
                ChapterWithHighlights(
                    chapter_id=chapter_id,
                    chapter_name=chapter.name if chapter else None,
                    chapter_number=chapter.chapter_number if chapter else None,
                    highlights=sorted(
                        grouped[chapter_id], key=lambda p: p.highlight.page or p.highlight.id.value
                    ),
                )
            )

        return results
