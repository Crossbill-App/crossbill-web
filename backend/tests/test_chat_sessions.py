"""Tests for chat session endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import AIChatSession as AIChatSessionModel
from src.models import Book, Chapter

CHAT_OPENER = "What do you want to chat about this chapter?"


async def create_chat_chapter(db_session: AsyncSession, book: Book) -> Chapter:
    """Create a chapter with xpoint data needed for content extraction."""
    chapter = Chapter(
        book_id=book.id,
        name="Chat Test Chapter",
        start_xpoint="/body/text/chapter[1]",
        end_xpoint="/body/text/chapter[2]",
    )
    db_session.add(chapter)
    await db_session.commit()
    await db_session.refresh(chapter)
    return chapter


class TestCreateChatSession:
    @patch("src.infrastructure.common.dependencies.is_ai_enabled", return_value=True)
    @patch("src.infrastructure.ai.ai_service.AIService._respond", new_callable=AsyncMock)
    @patch(
        "src.infrastructure.library.services.epub_text_extraction_service"
        ".EpubTextExtractionService.extract_chapter_text"
    )
    @patch(
        "src.infrastructure.library.repositories.file_repository.FileRepository.get_epub",
        new_callable=AsyncMock,
    )
    async def test_create_chat_session_success(
        self,
        mock_get_epub: AsyncMock,
        mock_extract: MagicMock,
        mock_respond: AsyncMock,
        mock_ai_enabled: MagicMock,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        test_book.ebook_file = "/path/to/test.epub"
        test_book.file_type = "epub"
        await db_session.commit()

        chapter = await create_chat_chapter(db_session, test_book)

        mock_get_epub.return_value = b"fake epub content"
        mock_extract.return_value = "The chapter is about testing."

        response = await client.post(f"/api/v1/chapters/{chapter.id}/chat-sessions")
        assert response.status_code == 201
        data = response.json()
        assert "session_id" in data
        assert data["message"] == CHAT_OPENER

        # The opener is fixed, not model-generated: no AI round-trip at session
        # start. Asserted on the funnel every AI call goes through, so it holds
        # whichever method a future change might reach for.
        mock_respond.assert_not_awaited()

        # The chapter content is seeded into the session history so the model can
        # refer to it on the first real message.
        session = (
            await db_session.execute(
                select(AIChatSessionModel).where(AIChatSessionModel.id == data["session_id"])
            )
        ).scalar_one()
        assert "The chapter is about testing." in str(session.message_history)

    @patch("src.infrastructure.common.dependencies.is_ai_enabled", return_value=True)
    async def test_create_chat_session_chapter_not_found(
        self, mock_ai_enabled: MagicMock, client: AsyncClient
    ) -> None:
        response = await client.post("/api/v1/chapters/99999/chat-sessions")
        assert response.status_code == 404


class TestSendChatMessage:
    @patch("src.infrastructure.common.dependencies.is_ai_enabled", return_value=True)
    async def test_send_message_session_not_found(
        self, mock_ai_enabled: MagicMock, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/api/v1/chat-sessions/99999/messages",
            json={"message": "Hi"},
        )
        assert response.status_code == 404

    @patch("src.infrastructure.common.dependencies.is_ai_enabled", return_value=True)
    async def test_send_empty_message_rejected(
        self, mock_ai_enabled: MagicMock, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/api/v1/chat-sessions/1/messages",
            json={"message": ""},
        )
        assert response.status_code == 422

    @patch("src.infrastructure.common.dependencies.is_ai_enabled", return_value=True)
    @patch(
        "src.infrastructure.ai.ai_service.AIService.continue_chat",
        new_callable=AsyncMock,
    )
    async def test_send_message_success(
        self,
        mock_continue_chat: AsyncMock,
        mock_ai_enabled: MagicMock,
        client: AsyncClient,
        db_session: AsyncSession,
        test_chapter: Chapter,
    ) -> None:
        chat_session = AIChatSessionModel(
            user_id=1,
            chapter_id=test_chapter.id,
            session_type="chat",
            message_history=[{"some": "history"}],
        )
        db_session.add(chat_session)
        await db_session.commit()
        await db_session.refresh(chat_session)

        mock_continue_chat.return_value = (
            "Sure — what interested you in this chapter?",
            [{"updated": "history"}],
        )

        response = await client.post(
            f"/api/v1/chat-sessions/{chat_session.id}/messages",
            json={"message": "Let's talk about the main theme"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Sure — what interested you in this chapter?"
