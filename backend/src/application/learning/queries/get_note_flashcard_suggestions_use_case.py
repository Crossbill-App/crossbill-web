"""Use case for AI-generated flashcard suggestions from note content."""

import structlog

from src.application.ai.ai_usage_context import AIUsageContext
from src.application.learning.protocols.ai_flashcard_service import (
    AIFlashcardServiceProtocol,
)
from src.application.learning.queries.flashcard_suggestions import FlashcardSuggestion
from src.application.notes.protocols.note_repository import NoteRepositoryProtocol
from src.application.reading.protocols.highlight_repository import HighlightRepositoryProtocol
from src.domain.common.value_objects.ids import HighlightId, NoteId, UserId
from src.domain.notes.exceptions import NoteNotFoundError

logger = structlog.get_logger(__name__)


class GetNoteFlashcardSuggestionsUseCase:
    """Use case for AI-generated flashcard suggestions from note content."""

    def __init__(
        self,
        note_repository: NoteRepositoryProtocol,
        highlight_repository: HighlightRepositoryProtocol,
        ai_flashcard_service: AIFlashcardServiceProtocol,
    ) -> None:
        self.note_repository = note_repository
        self.highlight_repository = highlight_repository
        self.ai_flashcard_service = ai_flashcard_service

    async def get_suggestions(self, note_id: int, user_id: int) -> list[FlashcardSuggestion]:
        """
        Get AI-generated flashcard suggestions from a note's content.

        The content sent to the AI combines the note's title, its markdown
        body, and the text of its linked highlights.

        Args:
            note_id: ID of the note
            user_id: ID of the user

        Returns:
            List of flashcard suggestions

        Raises:
            NoteNotFoundError: If note not found or not owned by user
        """
        user_id_vo = UserId(user_id)

        note = await self.note_repository.find_by_id(NoteId(note_id), user_id_vo)
        if not note:
            raise NoteNotFoundError(note_id)

        content_parts = [note.title]
        if note.body.strip():
            content_parts.append(note.body)
        for highlight_id in note.highlight_ids:
            highlight = await self.highlight_repository.find_by_id(
                HighlightId(highlight_id), user_id_vo
            )
            # Soft-deleted highlights keep their link rows but are hidden from display
            if highlight and highlight.deleted_at is None:
                content_parts.append(highlight.text)
        content = "\n\n".join(content_parts)

        usage_context = AIUsageContext(
            user_id=user_id_vo,
            task_type="flashcard_suggestions",
            entity_type="note",
            entity_id=note_id,
        )
        ai_suggestions = await self.ai_flashcard_service.generate_flashcard_suggestions(
            content, usage_context
        )

        suggestions = [
            FlashcardSuggestion(question=s.question, answer=s.answer) for s in ai_suggestions
        ]

        logger.info(
            "note_flashcard_suggestions_generated",
            note_id=note_id,
            suggestion_count=len(suggestions),
        )

        return suggestions
