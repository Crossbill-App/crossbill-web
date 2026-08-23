"""Tests for the chapter digest generation endpoint."""

from unittest.mock import MagicMock

from httpx import AsyncClient

from src.infrastructure.ai.ai_service import MAX_CHAPTER_CONTEXT_CHARS
from src.models import Chapter
from tests.ai_helpers import FakeAgent


class TestGenerateChapterDigest:
    async def test_caps_over_long_chapter_content(
        self,
        client: AsyncClient,
        ai_enabled: None,
        epub_chapter: Chapter,
        chapter_text: MagicMock,
        digest_agent: FakeAgent,
    ) -> None:
        chapter_text.return_value = "x" * (MAX_CHAPTER_CONTEXT_CHARS * 2)

        response = await client.post(f"/api/v1/chapters/{epub_chapter.id}/digest/generate")

        assert response.status_code == 201, response.text
        assert digest_agent.received_prompts == ["x" * MAX_CHAPTER_CONTEXT_CHARS]
