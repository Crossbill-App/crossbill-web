"""Shared domain-to-schema mappers for reading responses."""

from datetime import UTC, datetime

from src.domain.reading.services import ChapterWithHighlights as DomainChapterWithHighlights
from src.domain.reading.services.highlight_style_resolver import ResolvedLabel
from src.domain.tagging.entities.tag import Tag as DomainTag
from src.infrastructure.common.schemas.position_schemas import PositionResponse
from src.infrastructure.learning.schemas import Flashcard
from src.infrastructure.reading.schemas import (
    ChapterWithHighlights,
    Highlight,
    HighlightLabel,
    TagInBook,
)


def map_chapters_to_schemas(
    chapters_grouped: list[DomainChapterWithHighlights[DomainTag]],
    labels: dict[int, ResolvedLabel] | None = None,
) -> list[ChapterWithHighlights]:
    """
    Map domain ChapterWithHighlights to Pydantic schemas.

    Args:
        chapters_grouped: List of ChapterWithHighlights domain dataclasses
        labels: Optional dict mapping highlight_style_id -> ResolvedLabel

    Returns:
        List of ChapterWithHighlights Pydantic schemas
    """
    chapters_with_highlights = []

    for chapter_group in chapters_grouped:
        highlight_schemas = []
        for hw in chapter_group.highlights:
            h = hw.highlight
            chapter = hw.chapter

            resolved = (
                labels.get(h.highlight_style_id.value) if labels and h.highlight_style_id else None
            )
            highlight_schema = Highlight(
                id=h.id.value,
                book_id=h.book_id.value,
                chapter_id=h.chapter_id.value if h.chapter_id else None,
                text=h.text,
                chapter=chapter.name if chapter else None,
                chapter_number=chapter.chapter_number if chapter else None,
                page=h.page,
                datetime=h.datetime,
                label=HighlightLabel(
                    highlight_style_id=h.highlight_style_id.value if h.highlight_style_id else None,
                    text=resolved.label if resolved else None,
                    ui_color=resolved.ui_color if resolved else None,
                )
                if h.highlight_style_id
                else None,
                flashcards=[
                    Flashcard(
                        id=fc.id.value,
                        user_id=fc.user_id.value,
                        book_id=fc.book_id.value,
                        highlight_id=fc.highlight_id.value if fc.highlight_id else None,
                        chapter_id=fc.chapter_id.value if fc.chapter_id else None,
                        question=fc.question,
                        answer=fc.answer,
                    )
                    for fc in hw.flashcards
                ],
                tags=[
                    TagInBook(
                        id=tag.id.value,
                        name=tag.name,
                        tag_group_id=tag.tag_group_id,
                    )
                    for tag in hw.tags
                ],
                created_at=h.created_at,
                updated_at=h.updated_at,
            )
            highlight_schemas.append(highlight_schema)

        # Get chapter info from first highlight's chapter
        first_chapter = chapter_group.highlights[0].chapter if chapter_group.highlights else None

        chapter_with_highlights = ChapterWithHighlights(
            id=chapter_group.chapter_id,
            name=chapter_group.chapter_name or "",
            chapter_number=chapter_group.chapter_number,
            parent_id=chapter_group.parent_id,
            start_position=PositionResponse(
                index=chapter_group.start_position.index,
                char_index=chapter_group.start_position.char_index,
            )
            if chapter_group.start_position
            else None,
            highlights=highlight_schemas,
            created_at=first_chapter.created_at if first_chapter else datetime.now(UTC),
            updated_at=first_chapter.created_at if first_chapter else datetime.now(UTC),
        )
        chapters_with_highlights.append(chapter_with_highlights)

    return chapters_with_highlights
