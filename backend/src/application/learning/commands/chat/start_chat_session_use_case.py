from datetime import UTC, datetime

import structlog

from src.application.learning.protocols.ai_chat_service import AIChatServiceProtocol
from src.application.learning.protocols.ai_chat_session_repository import (
    AIChatSessionRepositoryProtocol,
)
from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.library.protocols.chapter_repository import ChapterRepositoryProtocol
from src.application.library.protocols.file_repository import FileRepositoryProtocol
from src.application.reading.protocols.ebook_text_extraction_service import (
    EbookTextExtractionServiceProtocol,
)
from src.domain.common.exceptions import DomainError
from src.domain.common.value_objects.ids import ChapterId, UserId
from src.domain.learning.entities.ai_chat_session import AIChatSession
from src.domain.reading.exceptions import BookNotFoundError, ChapterNotFoundError

logger = structlog.get_logger(__name__)

CHAT_OPENER = "What do you want to chat about this chapter?"


class StartChatSessionUseCase:
    def __init__(
        self,
        ai_chat_session_repository: AIChatSessionRepositoryProtocol,
        chapter_repo: ChapterRepositoryProtocol,
        book_repo: BookRepositoryProtocol,
        file_repo: FileRepositoryProtocol,
        text_extraction_service: EbookTextExtractionServiceProtocol,
        ai_chat_service: AIChatServiceProtocol,
    ) -> None:
        self.ai_chat_session_repo = ai_chat_session_repository
        self.chapter_repo = chapter_repo
        self.book_repo = book_repo
        self.file_repo = file_repo
        self.text_extraction = text_extraction_service
        self.ai_chat_service = ai_chat_service

    async def start(self, chapter_id: int, user_id: int) -> tuple[int, str]:
        """Start a new chat session for a chapter.

        Returns:
            Tuple of (session_id, first_question)
        """
        chapter_id_vo = ChapterId(chapter_id)
        user_id_vo = UserId(user_id)

        # 1. Verify chapter exists and user owns it
        chapter = await self.chapter_repo.find_by_id(chapter_id_vo, user_id_vo)
        if not chapter:
            raise ChapterNotFoundError(chapter_id)

        # 2. Extract chapter content
        if not chapter.start_xpoint:
            raise DomainError(
                "Chapter does not have position data. EPUB must be uploaded with chapter positions."
            )

        book = await self.book_repo.find_by_id(chapter.book_id, user_id_vo)
        if not book or not book.ebook_file or book.file_type != "epub":
            raise BookNotFoundError(chapter.book_id.value)

        epub_content = await self.file_repo.get_epub(book.ebook_file)
        if not epub_content:
            raise BookNotFoundError(chapter.book_id.value)

        content = self.text_extraction.extract_chapter_text(
            epub_content=epub_content,
            start_xpoint=chapter.start_xpoint,
            end_xpoint=chapter.end_xpoint,
        )

        # 3. Create AI chat session
        session = AIChatSession.create(
            user_id=user_id_vo,
            chapter_id=chapter_id_vo,
            session_type="chat",
            created_at=datetime.now(UTC),
        )

        # 4. Seed the message history with the chapter content (no AI round-trip);
        #    the model reads it when the reader sends their first message.
        session.message_history = self.ai_chat_service.seed_chat_context(content, CHAT_OPENER)
        saved_session = await self.ai_chat_session_repo.create(session)

        logger.info(
            "chat_session_started",
            session_id=saved_session.id.value,
            chapter_id=chapter_id,
        )

        return saved_session.id.value, CHAT_OPENER
