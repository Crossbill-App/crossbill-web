"""Response-schema builders for the shared highlight row.

Lives beside the schema it produces so that every router rendering a highlight
-- book details, in-book search -- gets the same field mapping.
"""

from src.application.common.queries.highlight_row import HighlightRow
from src.infrastructure.learning.schemas.flashcard_schemas import Flashcard
from src.infrastructure.reading.schemas.highlight_schemas import Highlight, HighlightLabel
from src.infrastructure.tagging.schemas.tag_schemas import TagInBook


def build_highlight_schema(highlight: HighlightRow) -> Highlight:
    """Build the Highlight schema from a highlight in a read model."""
    return Highlight(
        id=highlight.id,
        book_id=highlight.book_id,
        chapter_id=highlight.chapter_id,
        text=highlight.text,
        chapter=highlight.chapter_name,
        chapter_number=highlight.chapter_number,
        page=highlight.page,
        datetime=highlight.datetime,
        label=HighlightLabel(
            highlight_style_id=highlight.label.highlight_style_id,
            text=highlight.label.text,
            ui_color=highlight.label.ui_color,
        )
        if highlight.label
        else None,
        removed_from_devices=highlight.removed_from_devices,
        flashcards=[
            Flashcard(
                id=card.id,
                user_id=card.user_id,
                book_id=card.book_id,
                highlight_id=card.highlight_id,
                chapter_id=card.chapter_id,
                note_id=card.note_id,
                question=card.question,
                answer=card.answer,
            )
            for card in highlight.flashcards
        ],
        tags=[
            TagInBook(id=tag.id, name=tag.name, tag_group_id=tag.tag_group_id)
            for tag in highlight.tags
        ],
        created_at=highlight.created_at,
        updated_at=highlight.updated_at,
    )
