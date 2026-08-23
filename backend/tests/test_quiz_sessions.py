"""Tests for quiz session endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.ai.ai_service import MAX_CHAPTER_CONTEXT_CHARS
from src.models import AIChatSession as AIChatSessionModel
from src.models import Book, Chapter
from tests.ai_helpers import FakeAgent


class TestCreateQuizSession:
    async def test_create_quiz_session_success(
        self,
        client: AsyncClient,
        ai_enabled: None,
        epub_chapter: Chapter,
        chapter_text: MagicMock,
        quiz_agent: FakeAgent,
    ) -> None:
        chapter_text.return_value = "Chapter content here"

        response = await client.post(f"/api/v1/chapters/{epub_chapter.id}/quiz-sessions")

        assert response.status_code == 201, response.text
        data = response.json()
        assert "session_id" in data
        assert "Question 1/5" in data["message"]

    async def test_create_quiz_session_caps_over_long_chapter_content(
        self,
        client: AsyncClient,
        ai_enabled: None,
        epub_chapter: Chapter,
        chapter_text: MagicMock,
        quiz_agent: FakeAgent,
    ) -> None:
        chapter_text.return_value = "x" * (MAX_CHAPTER_CONTEXT_CHARS * 2)

        response = await client.post(f"/api/v1/chapters/{epub_chapter.id}/quiz-sessions")

        assert response.status_code == 201, response.text
        # The cap applies to the chapter content, not to the whole prompt, which
        # also carries the fixed instruction text around it -- so assert on the
        # content rather than on a prompt length that moves with the wording.
        [prompt] = quiz_agent.received_prompts
        assert "x" * MAX_CHAPTER_CONTEXT_CHARS in prompt
        assert "x" * (MAX_CHAPTER_CONTEXT_CHARS + 1) not in prompt

    async def test_create_quiz_session_chapter_not_found(
        self, client: AsyncClient, ai_enabled: None
    ) -> None:
        response = await client.post("/api/v1/chapters/99999/quiz-sessions")
        assert response.status_code == 404


class TestSendQuizMessage:
    async def test_send_message_session_not_found(
        self, client: AsyncClient, ai_enabled: None
    ) -> None:
        response = await client.post(
            "/api/v1/quiz-sessions/99999/messages",
            json={"message": "My answer"},
        )
        assert response.status_code == 404

    async def test_send_empty_message_rejected(self, client: AsyncClient, ai_enabled: None) -> None:
        response = await client.post(
            "/api/v1/quiz-sessions/1/messages",
            json={"message": ""},
        )
        assert response.status_code == 422

    @patch(
        "src.infrastructure.ai.ai_service.AIService.continue_quiz",
        new_callable=AsyncMock,
    )
    async def test_send_message_success(
        self,
        mock_continue_quiz: AsyncMock,
        client: AsyncClient,
        ai_enabled: None,
        db_session: AsyncSession,
        test_book: Book,
        epub_chapter: Chapter,
    ) -> None:
        ai_chat_session = AIChatSessionModel(
            user_id=1,
            chapter_id=epub_chapter.id,
            session_type="quiz",
            message_history=[{"some": "history"}],
        )
        db_session.add(ai_chat_session)
        await db_session.commit()
        await db_session.refresh(ai_chat_session)

        mock_continue_quiz.return_value = (
            "Good answer! **Question 2/5:** What happened next?",
            [{"updated": "history"}],
        )

        response = await client.post(
            f"/api/v1/quiz-sessions/{ai_chat_session.id}/messages",
            json={"message": "The main topic is testing"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "Question 2/5" in data["message"]
