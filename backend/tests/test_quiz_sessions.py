"""Tests for quiz session endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.ai.ai_service import MAX_CHAPTER_CONTEXT_CHARS
from src.models import AIChatSession as AIChatSessionModel
from src.models import Book, Chapter


async def create_quiz_chapter(db_session: AsyncSession, book: Book) -> Chapter:
    """Create a chapter with xpoint data needed for content extraction."""
    chapter = Chapter(
        book_id=book.id,
        name="Quiz Test Chapter",
        start_xpoint="/body/text/chapter[1]",
        end_xpoint="/body/text/chapter[2]",
    )
    db_session.add(chapter)
    await db_session.commit()
    await db_session.refresh(chapter)
    return chapter


class TestCreateQuizSession:
    @patch("src.infrastructure.common.dependencies.is_ai_enabled", return_value=True)
    @patch("src.infrastructure.ai.ai_service.AIService.start_quiz", new_callable=AsyncMock)
    @patch(
        "src.infrastructure.library.services.epub_text_extraction_service"
        ".EpubTextExtractionService.extract_chapter_text"
    )
    @patch(
        "src.infrastructure.library.repositories.file_repository.FileRepository.get_epub",
        new_callable=AsyncMock,
    )
    async def test_create_quiz_session_success(
        self,
        mock_get_epub: AsyncMock,
        mock_extract: MagicMock,
        mock_start_quiz: AsyncMock,
        mock_ai_enabled: MagicMock,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        test_book.ebook_file = "/path/to/test.epub"
        test_book.file_type = "epub"
        await db_session.commit()

        chapter = await create_quiz_chapter(db_session, test_book)

        mock_get_epub.return_value = b"fake epub content"
        mock_extract.return_value = "Chapter content here"

        mock_start_quiz.return_value = (
            "**Question 1/5:** What is the main topic?",
            [{"some": "history"}],
        )

        response = await client.post(f"/api/v1/chapters/{chapter.id}/quiz-sessions")
        assert response.status_code == 201
        data = response.json()
        assert "session_id" in data
        assert "message" in data
        assert "Question 1/5" in data["message"]

    @patch("src.infrastructure.common.dependencies.is_ai_enabled", return_value=True)
    @patch("src.infrastructure.ai.ai_service.get_quiz_agent")
    @patch("src.infrastructure.ai.ai_service.AIService._respond", new_callable=AsyncMock)
    @patch(
        "src.infrastructure.library.services.epub_text_extraction_service"
        ".EpubTextExtractionService.extract_chapter_text"
    )
    @patch(
        "src.infrastructure.library.repositories.file_repository.FileRepository.get_epub",
        new_callable=AsyncMock,
    )
    async def test_create_quiz_session_caps_over_long_chapter_content(
        self,
        mock_get_epub: AsyncMock,
        mock_extract: MagicMock,
        mock_respond: AsyncMock,
        mock_get_agent: MagicMock,
        mock_ai_enabled: MagicMock,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        test_book.ebook_file = "/path/to/test.epub"
        test_book.file_type = "epub"
        await db_session.commit()

        chapter = await create_quiz_chapter(db_session, test_book)

        mock_get_epub.return_value = b"fake epub content"
        mock_extract.return_value = "x" * (MAX_CHAPTER_CONTEXT_CHARS * 2)
        mock_respond.return_value = ("**Question 1/5:** ?", [{"some": "history"}])

        response = await client.post(f"/api/v1/chapters/{chapter.id}/quiz-sessions")
        assert response.status_code == 201

        prompt = mock_respond.call_args.kwargs["prompt"]
        # The cap applies to the chapter content itself, not the whole prompt
        # (which also carries the fixed instruction text around it).
        assert len(prompt) < MAX_CHAPTER_CONTEXT_CHARS + 250

    @patch("src.infrastructure.common.dependencies.is_ai_enabled", return_value=True)
    async def test_create_quiz_session_chapter_not_found(
        self, mock_ai_enabled: MagicMock, client: AsyncClient
    ) -> None:
        response = await client.post("/api/v1/chapters/99999/quiz-sessions")
        assert response.status_code == 404


class TestSendQuizMessage:
    @patch("src.infrastructure.common.dependencies.is_ai_enabled", return_value=True)
    async def test_send_message_session_not_found(
        self, mock_ai_enabled: MagicMock, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/api/v1/quiz-sessions/99999/messages",
            json={"message": "My answer"},
        )
        assert response.status_code == 404

    @patch("src.infrastructure.common.dependencies.is_ai_enabled", return_value=True)
    async def test_send_empty_message_rejected(
        self, mock_ai_enabled: MagicMock, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/api/v1/quiz-sessions/1/messages",
            json={"message": ""},
        )
        assert response.status_code == 422

    @patch("src.infrastructure.common.dependencies.is_ai_enabled", return_value=True)
    @patch(
        "src.infrastructure.ai.ai_service.AIService.continue_quiz",
        new_callable=AsyncMock,
    )
    async def test_send_message_success(
        self,
        mock_continue_quiz: AsyncMock,
        mock_ai_enabled: MagicMock,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        chapter = await create_quiz_chapter(db_session, test_book)

        ai_chat_session = AIChatSessionModel(
            user_id=1,
            chapter_id=chapter.id,
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
        assert "message" in data
        assert "Question 2/5" in data["message"]
