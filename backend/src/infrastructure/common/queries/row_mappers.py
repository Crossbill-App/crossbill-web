"""ORM-to-DTO mapping for the view DTOs shared across read models.

Nothing here decides anything: a highlight's effective label arrives already
resolved from the caller's ``LabelResolutionService``, so the rule stays where
the domain put it (ADR-0001, rule 1).
"""

from src.application.common.queries.highlight_row import HighlightLabelView, HighlightRow
from src.application.common.queries.refs import FlashcardRef, TagRef
from src.domain.reading.services.highlight_style_resolver import ResolvedLabel
from src.infrastructure.learning.orm.flashcard_model import Flashcard as FlashcardORM
from src.infrastructure.reading.orm.highlight_model import Highlight as HighlightORM
from src.infrastructure.tagging.orm.tag_model import Tag as TagORM


def tag_ref(row: TagORM) -> TagRef:
    """Map a tag row to its view DTO."""
    return TagRef(id=row.id, name=row.name, tag_group_id=row.tag_group_id)


def flashcard_ref(row: FlashcardORM) -> FlashcardRef:
    """Map a flashcard row to its view DTO."""
    return FlashcardRef(
        id=row.id,
        user_id=row.user_id,
        book_id=row.book_id,
        highlight_id=row.highlight_id,
        chapter_id=row.chapter_id,
        note_id=row.note_id,
        question=row.question,
        answer=row.answer,
    )


def highlight_row(row: HighlightORM, labels: dict[int, ResolvedLabel]) -> HighlightRow:
    """Map a highlight row and its eagerly loaded relations to the view DTO."""
    style_id = row.highlight_style_id
    resolved = labels.get(style_id) if style_id is not None else None
    return HighlightRow(
        id=row.id,
        book_id=row.book_id,
        chapter_id=row.chapter_id,
        chapter_name=row.chapter.name if row.chapter else None,
        chapter_number=row.chapter.chapter_number if row.chapter else None,
        text=row.text,
        page=row.page,
        datetime=row.datetime,
        label=HighlightLabelView(
            highlight_style_id=style_id,
            text=resolved.label if resolved else None,
            ui_color=resolved.ui_color if resolved else None,
        )
        if style_id is not None
        else None,
        removed_from_devices=row.removed_from_devices_at is not None,
        tags=tuple(tag_ref(tag) for tag in row.tags),
        flashcards=tuple(flashcard_ref(card) for card in row.flashcards),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
