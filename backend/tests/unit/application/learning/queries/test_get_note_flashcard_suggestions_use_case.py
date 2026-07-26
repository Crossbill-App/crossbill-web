"""Tests for GetNoteFlashcardSuggestionsUseCase."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from src.application.learning.protocols.ai_flashcard_service import AIFlashcardSuggestion
from src.application.learning.queries.get_note_flashcard_suggestions_use_case import (
    GetNoteFlashcardSuggestionsUseCase,
)
from src.domain.common.value_objects.ids import BookId, HighlightId, NoteId, UserId
from src.domain.notes.entities.note import Note
from src.domain.notes.exceptions import NoteNotFoundError
from src.domain.reading.entities.highlight import Highlight


def _make_note(
    note_id: int = 1,
    title: str = "Raskolnikov",
    body: str = "The novel's protagonist.",
    highlight_ids: list[int] | None = None,
) -> Note:
    now = datetime.now(UTC)
    return Note.create_with_id(
        id=NoteId(note_id),
        user_id=UserId(1),
        title=title,
        body=body,
        kind=None,
        created_at=now,
        updated_at=now,
        book_ids=[1],
        chapter_ids=[],
        highlight_ids=highlight_ids or [],
        tag_ids=[],
    )


def _make_highlight(highlight_id: int, text: str, deleted: bool = False) -> Highlight:
    highlight = Highlight.create(
        user_id=UserId(1),
        book_id=BookId(1),
        text=text,
    )
    highlight.id = HighlightId(highlight_id)
    if deleted:
        highlight.deleted_at = datetime.now(UTC)
    return highlight


class TestGetNoteFlashcardSuggestionsUseCase:
    @pytest.fixture
    def note_repository(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def highlight_repository(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def ai_flashcard_service(self) -> AsyncMock:
        service = AsyncMock()
        service.generate_flashcard_suggestions.return_value = [
            AIFlashcardSuggestion(question="Q1", answer="A1"),
            AIFlashcardSuggestion(question="Q2", answer="A2"),
        ]
        return service

    @pytest.fixture
    def use_case(
        self,
        note_repository: AsyncMock,
        highlight_repository: AsyncMock,
        ai_flashcard_service: AsyncMock,
    ) -> GetNoteFlashcardSuggestionsUseCase:
        return GetNoteFlashcardSuggestionsUseCase(
            note_repository=note_repository,
            highlight_repository=highlight_repository,
            ai_flashcard_service=ai_flashcard_service,
        )

    async def test_note_not_found_raises(
        self,
        use_case: GetNoteFlashcardSuggestionsUseCase,
        note_repository: AsyncMock,
    ) -> None:
        note_repository.find_by_id.return_value = None

        with pytest.raises(NoteNotFoundError):
            await use_case.get_suggestions(note_id=99, user_id=1)

    async def test_content_combines_title_body_and_highlights(
        self,
        use_case: GetNoteFlashcardSuggestionsUseCase,
        note_repository: AsyncMock,
        highlight_repository: AsyncMock,
        ai_flashcard_service: AsyncMock,
    ) -> None:
        note_repository.find_by_id.return_value = _make_note(highlight_ids=[10, 11])
        highlight_repository.find_by_id.side_effect = [
            _make_highlight(10, "First highlight text"),
            _make_highlight(11, "Second highlight text"),
        ]

        suggestions = await use_case.get_suggestions(note_id=1, user_id=1)

        content = ai_flashcard_service.generate_flashcard_suggestions.call_args.args[0]
        assert content == (
            "Raskolnikov\n\nThe novel's protagonist.\n\n"
            "First highlight text\n\nSecond highlight text"
        )
        assert [(s.question, s.answer) for s in suggestions] == [("Q1", "A1"), ("Q2", "A2")]

    async def test_skips_missing_and_soft_deleted_highlights(
        self,
        use_case: GetNoteFlashcardSuggestionsUseCase,
        note_repository: AsyncMock,
        highlight_repository: AsyncMock,
        ai_flashcard_service: AsyncMock,
    ) -> None:
        note_repository.find_by_id.return_value = _make_note(highlight_ids=[10, 11, 12])
        highlight_repository.find_by_id.side_effect = [
            None,
            _make_highlight(11, "Kept highlight", deleted=True),
            _make_highlight(12, "Surviving highlight"),
        ]

        await use_case.get_suggestions(note_id=1, user_id=1)

        content = ai_flashcard_service.generate_flashcard_suggestions.call_args.args[0]
        assert "Kept highlight" not in content
        assert "Surviving highlight" in content

    async def test_empty_body_is_omitted(
        self,
        use_case: GetNoteFlashcardSuggestionsUseCase,
        note_repository: AsyncMock,
        ai_flashcard_service: AsyncMock,
    ) -> None:
        note_repository.find_by_id.return_value = _make_note(body="   ")

        await use_case.get_suggestions(note_id=1, user_id=1)

        content = ai_flashcard_service.generate_flashcard_suggestions.call_args.args[0]
        assert content == "Raskolnikov"

    async def test_usage_context_uses_note_entity(
        self,
        use_case: GetNoteFlashcardSuggestionsUseCase,
        note_repository: AsyncMock,
        ai_flashcard_service: AsyncMock,
    ) -> None:
        note_repository.find_by_id.return_value = _make_note(note_id=42)

        await use_case.get_suggestions(note_id=42, user_id=7)

        usage_context = ai_flashcard_service.generate_flashcard_suggestions.call_args.args[1]
        assert usage_context.entity_type == "note"
        assert usage_context.entity_id == 42
        assert usage_context.task_type == "flashcard_suggestions"
        assert usage_context.user_id == UserId(7)
