"""Tests for chat session endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.ai.ai_service import MAX_CHAPTER_CONTEXT_CHARS
from src.models import AIChatSession as AIChatSessionModel
from src.models import Chapter

CHAT_OPENER = "What do you want to chat about this chapter?"


async def seeded_history(db_session: AsyncSession, session_id: int) -> str:
    """The message history the endpoint stored, as one searchable string."""
    session = (
        await db_session.execute(
            select(AIChatSessionModel).where(AIChatSessionModel.id == session_id)
        )
    ).scalar_one()
    return str(session.message_history)


class TestCreateChatSession:
    @patch("src.infrastructure.ai.ai_service.AIService._respond", new_callable=AsyncMock)
    async def test_create_chat_session_success(
        self,
        mock_respond: AsyncMock,
        client: AsyncClient,
        ai_enabled: None,
        db_session: AsyncSession,
        epub_chapter: Chapter,
        chapter_text: MagicMock,
    ) -> None:
        chapter_text.return_value = "The chapter is about testing."

        response = await client.post(f"/api/v1/chapters/{epub_chapter.id}/chat-sessions")

        assert response.status_code == 201, response.text
        data = response.json()
        assert "session_id" in data
        assert data["message"] == CHAT_OPENER

        # The opener is fixed, not model-generated: no AI round-trip at session
        # start. Asserted on the funnel every AI call goes through, so it holds
        # whichever method a future change might reach for.
        mock_respond.assert_not_awaited()

        # The chapter content is seeded into the session history so the model can
        # refer to it on the first real message.
        assert "The chapter is about testing." in await seeded_history(
            db_session, data["session_id"]
        )

    async def test_create_chat_session_caps_over_long_chapter_content(
        self,
        client: AsyncClient,
        ai_enabled: None,
        db_session: AsyncSession,
        epub_chapter: Chapter,
        chapter_text: MagicMock,
    ) -> None:
        """The seed is persisted and replayed on every turn, so an uncapped one
        re-sends the whole book with each message the reader writes."""
        chapter_text.return_value = "x" * (MAX_CHAPTER_CONTEXT_CHARS * 2)

        response = await client.post(f"/api/v1/chapters/{epub_chapter.id}/chat-sessions")

        assert response.status_code == 201, response.text
        seeded = await seeded_history(db_session, response.json()["session_id"])
        assert "x" * MAX_CHAPTER_CONTEXT_CHARS in seeded
        assert "x" * (MAX_CHAPTER_CONTEXT_CHARS + 1) not in seeded

    async def test_create_chat_session_chapter_not_found(
        self, client: AsyncClient, ai_enabled: None
    ) -> None:
        response = await client.post("/api/v1/chapters/99999/chat-sessions")
        assert response.status_code == 404


class TestSendChatMessage:
    async def test_send_message_session_not_found(
        self, client: AsyncClient, ai_enabled: None
    ) -> None:
        response = await client.post(
            "/api/v1/chat-sessions/99999/messages",
            json={"message": "Hi"},
        )
        assert response.status_code == 404

    async def test_send_empty_message_rejected(self, client: AsyncClient, ai_enabled: None) -> None:
        response = await client.post(
            "/api/v1/chat-sessions/1/messages",
            json={"message": ""},
        )
        assert response.status_code == 422

    @patch(
        "src.infrastructure.ai.ai_service.AIService.continue_chat",
        new_callable=AsyncMock,
    )
    async def test_send_message_success(
        self,
        mock_continue_chat: AsyncMock,
        client: AsyncClient,
        ai_enabled: None,
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
