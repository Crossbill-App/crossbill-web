"""Tests for the chapter digest generation endpoint.

Digest generation was the one AI feature that already capped its input
(`content[:10000]`); these tests cover it going through the shared
`truncate_chapter_content` helper instead, alongside quiz and chat.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.ai.ai_service import MAX_CHAPTER_CONTEXT_CHARS
from src.models import Book, Chapter


async def create_digest_chapter(db_session: AsyncSession, book: Book) -> Chapter:
    """Create a chapter with xpoint data needed for content extraction."""
    chapter = Chapter(
        book_id=book.id,
        name="Digest Test Chapter",
        start_xpoint="/body/text/chapter[1]",
        end_xpoint="/body/text/chapter[2]",
    )
    db_session.add(chapter)
    await db_session.commit()
    await db_session.refresh(chapter)
    return chapter


class _FakeDigestResult:
    """Stands in for pydantic_ai's AgentRunResult, recording what it was run with."""

    def __init__(self, prompt: str) -> None:
        self.prompt = prompt
        self.output = SimpleNamespace(
            summary="A summary.",
            keypoints=["A key point."],
            questions_and_answers=[SimpleNamespace(question="Q?", answer="A.")],
        )
        self.response = SimpleNamespace(model_name="fake-model")

    def usage(self) -> SimpleNamespace:
        return SimpleNamespace(input_tokens=1, output_tokens=1)


class _FakeDigestAgent:
    def __init__(self) -> None:
        self.received_prompts: list[str] = []

    async def run(self, prompt: str) -> _FakeDigestResult:
        self.received_prompts.append(prompt)
        return _FakeDigestResult(prompt)


class TestGenerateChapterDigest:
    @patch("src.infrastructure.common.dependencies.is_ai_enabled", return_value=True)
    @patch(
        "src.application.semantic.services.embedding_enqueuer.EmbeddingEnqueuer.enqueue_for",
        new_callable=AsyncMock,
    )
    @patch("src.infrastructure.ai.ai_service.get_digest_agent")
    @patch(
        "src.infrastructure.library.services.epub_text_extraction_service"
        ".EpubTextExtractionService.extract_chapter_text"
    )
    @patch(
        "src.infrastructure.library.repositories.file_repository.FileRepository.get_epub",
        new_callable=AsyncMock,
    )
    async def test_generate_digest_caps_over_long_chapter_content(
        self,
        mock_get_epub: AsyncMock,
        mock_extract: MagicMock,
        mock_get_agent: MagicMock,
        mock_enqueue: AsyncMock,
        mock_ai_enabled: MagicMock,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        test_book.ebook_file = "/path/to/test.epub"
        test_book.file_type = "epub"
        await db_session.commit()

        chapter = await create_digest_chapter(db_session, test_book)

        mock_get_epub.return_value = b"fake epub content"
        mock_extract.return_value = "x" * (MAX_CHAPTER_CONTEXT_CHARS * 2)
        fake_agent = _FakeDigestAgent()
        mock_get_agent.return_value = fake_agent

        response = await client.post(f"/api/v1/chapters/{chapter.id}/digest/generate")

        assert response.status_code == 201
        assert len(fake_agent.received_prompts) == 1
        assert len(fake_agent.received_prompts[0]) == MAX_CHAPTER_CONTEXT_CHARS

    @patch("src.infrastructure.common.dependencies.is_ai_enabled", return_value=True)
    @patch(
        "src.application.semantic.services.embedding_enqueuer.EmbeddingEnqueuer.enqueue_for",
        new_callable=AsyncMock,
    )
    @patch("src.infrastructure.ai.ai_service.get_digest_agent")
    @patch(
        "src.infrastructure.library.services.epub_text_extraction_service"
        ".EpubTextExtractionService.extract_chapter_text"
    )
    @patch(
        "src.infrastructure.library.repositories.file_repository.FileRepository.get_epub",
        new_callable=AsyncMock,
    )
    async def test_generate_digest_leaves_short_chapter_content_untouched(
        self,
        mock_get_epub: AsyncMock,
        mock_extract: MagicMock,
        mock_get_agent: MagicMock,
        mock_enqueue: AsyncMock,
        mock_ai_enabled: MagicMock,
        client: AsyncClient,
        db_session: AsyncSession,
        test_book: Book,
    ) -> None:
        test_book.ebook_file = "/path/to/test.epub"
        test_book.file_type = "epub"
        await db_session.commit()

        chapter = await create_digest_chapter(db_session, test_book)

        mock_get_epub.return_value = b"fake epub content"
        short_content = "This chapter is short but long enough to pass the minimum-length check."
        mock_extract.return_value = short_content
        fake_agent = _FakeDigestAgent()
        mock_get_agent.return_value = fake_agent

        response = await client.post(f"/api/v1/chapters/{chapter.id}/digest/generate")

        assert response.status_code == 201
        assert fake_agent.received_prompts == [short_content]
