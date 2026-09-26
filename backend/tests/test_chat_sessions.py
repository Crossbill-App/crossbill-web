"""Tests for chat session endpoints."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.ai.ai_service import MAX_CHAPTER_CONTEXT_CHARS
from src.models import AIChatSession as AIChatSessionModel
from src.models import Chapter
from tests.ai_helpers import FakeAgent, seeded_history
from tests.fakes import FakeTextExtraction

CHAT_OPENER = "What do you want to chat about this chapter?"


class TestCreateChatSession:
    async def test_create_chat_session_success(
        self,
        client: AsyncClient,
        ai_enabled: None,
        db_session: AsyncSession,
        epub_chapter: Chapter,
        chapter_text: FakeTextExtraction,
        chat_agent: FakeAgent,
    ) -> None:
        chapter_text.text = "The chapter is about testing."

        response = await client.post(f"/api/v1/chapters/{epub_chapter.id}/chat-sessions")

        assert response.status_code == 201, response.text
        data = response.json()
        assert "session_id" in data
        assert data["message"] == CHAT_OPENER

        # The opener is fixed, not model-generated: no AI round-trip at session start.
        assert chat_agent.received_prompts == []

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
        chapter_text: FakeTextExtraction,
    ) -> None:
        """The seed is persisted and replayed on every turn, so an uncapped one
        re-sends the whole book with each message the reader writes."""
        chapter_text.text = "x" * (MAX_CHAPTER_CONTEXT_CHARS * 2)

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

    async def test_send_message_success(
        self,
        client: AsyncClient,
        ai_enabled: None,
        db_session: AsyncSession,
        test_chapter: Chapter,
        chat_agent: FakeAgent,
    ) -> None:
        chat_session = AIChatSessionModel(
            user_id=1,
            chapter_id=test_chapter.id,
            session_type="chat",
            message_history=[],
        )
        db_session.add(chat_session)
        await db_session.commit()
        await db_session.refresh(chat_session)
        chat_agent.output = "Sure — what interested you in this chapter?"

        response = await client.post(
            f"/api/v1/chat-sessions/{chat_session.id}/messages",
            json={"message": "Let's talk about the main theme"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Sure — what interested you in this chapter?"
        assert chat_agent.received_prompts == ["Let's talk about the main theme"]
        assert "Let's talk about the main theme" in await seeded_history(
            db_session, chat_session.id
        )
