from typing import Any

import boto3
from dependency_injector import containers, providers
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.reading.services.label_resolution_service import LabelResolutionService
from src.domain.reading.services.deduplication_service import HighlightDeduplicationService
from src.domain.reading.services.highlight_style_resolver import HighlightStyleResolver
from src.infrastructure.ai.ai_service import AIService
from src.infrastructure.ai.repositories.ai_usage_repository import AIUsageRepository
from src.infrastructure.identity.repositories.refresh_token_repository import RefreshTokenRepository
from src.infrastructure.identity.repositories.user_repository import UserRepository
from src.infrastructure.identity.services.password_service_adapter import PasswordServiceAdapter
from src.infrastructure.identity.services.token_service_adapter import TokenServiceAdapter
from src.infrastructure.jobs.queries.job_batch_query import JobBatchQuery
from src.infrastructure.jobs.repositories.job_batch_repository import JobBatchRepository
from src.infrastructure.learning.queries.book_flashcard_query import BookFlashcardQuery
from src.infrastructure.learning.repositories.ai_chat_session_repository import (
    AIChatSessionRepository,
)
from src.infrastructure.learning.repositories.flashcard_repository import FlashcardRepository
from src.infrastructure.library.queries.book_details_query import BookDetailsQuery
from src.infrastructure.library.repositories import BookRepository
from src.infrastructure.library.repositories.chapter_repository import ChapterRepository
from src.infrastructure.library.repositories.file_repository import FileRepository
from src.infrastructure.library.repositories.s3_file_repository import S3FileRepository
from src.infrastructure.library.services.cover_image_service import CoverImageService
from src.infrastructure.library.services.epub_parser_service import EpubParserService
from src.infrastructure.library.services.epub_position_index_service import (
    EpubPositionIndexService,
)
from src.infrastructure.library.services.epub_text_extraction_service import (
    EpubTextExtractionService,
)
from src.infrastructure.notes.queries.note_query import NoteQuery
from src.infrastructure.notes.repositories.note_repository import NoteRepository
from src.infrastructure.reading.repositories import (
    BookmarkRepository,
    HighlightRepository,
    HighlightStyleRepository,
)
from src.infrastructure.reading.repositories.chapter_prereading_repository import (
    ChapterPrereadingRepository,
)
from src.infrastructure.reading.repositories.reading_session_repository import (
    ReadingSessionRepository,
)
from src.infrastructure.reflection.repositories.book_reflection_repository import (
    BookReflectionRepository,
)
from src.infrastructure.tagging.repositories import TagRepository


def _create_s3_file_repository(settings: Any) -> S3FileRepository:  # noqa: ANN401
    """Create an S3FileRepository with a configured boto3 client."""
    client = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        region_name=settings.S3_REGION,
    )
    return S3FileRepository(s3_client=client, bucket_name=settings.S3_BUCKET_NAME)


class SharedContainer(containers.DeclarativeContainer):
    """Shared repositories, infrastructure services, and domain services."""

    db = providers.Dependency(instance_of=AsyncSession)
    settings = providers.Dependency()

    # Repositories
    book_repository = providers.Factory(BookRepository, db=db)
    bookmark_repository = providers.Factory(BookmarkRepository, db=db)
    highlight_repository = providers.Factory(HighlightRepository, db=db)
    tag_repository = providers.Factory(TagRepository, db=db)
    chapter_repository = providers.Factory(ChapterRepository, db=db)
    note_repository = providers.Factory(NoteRepository, db=db)
    book_reflection_repository = providers.Factory(BookReflectionRepository, db=db)
    reading_session_repository = providers.Factory(ReadingSessionRepository, db=db)
    flashcard_repository = providers.Factory(FlashcardRepository, db=db)
    chapter_prereading_repository = providers.Factory(ChapterPrereadingRepository, db=db)
    highlight_style_repository = providers.Factory(HighlightStyleRepository, db=db)
    file_repository = providers.Selector(
        providers.Callable(
            lambda settings: "s3" if settings.s3_enabled else "local", settings=settings
        ),
        s3=providers.Singleton(
            _create_s3_file_repository,
            settings=settings,
        ),
        local=providers.Factory(FileRepository),
    )

    # AI
    ai_usage_repository = providers.Factory(AIUsageRepository, db=db)
    ai_service = providers.Factory(AIService, usage_repository=ai_usage_repository)

    # Infrastructure services (no db dependency)
    epub_parser_service = providers.Factory(EpubParserService)
    epub_position_index_service = providers.Factory(EpubPositionIndexService)
    ebook_text_extraction_service = providers.Factory(EpubTextExtractionService)
    cover_image_service = providers.Factory(CoverImageService)

    # Identity services
    user_repository = providers.Factory(UserRepository, db=db)
    password_service = providers.Singleton(PasswordServiceAdapter)
    token_service = providers.Singleton(TokenServiceAdapter)
    refresh_token_repository = providers.Factory(RefreshTokenRepository, db=db)

    # Domain services
    highlight_deduplication_service = providers.Factory(HighlightDeduplicationService)
    highlight_style_resolver = providers.Factory(HighlightStyleResolver)

    # Application services (with deps)
    label_resolution_service = providers.Factory(
        LabelResolutionService,
        highlight_style_repository=highlight_style_repository,
        highlight_style_resolver=highlight_style_resolver,
    )

    # Query services (read models); like repositories, these take the session
    book_details_query = providers.Factory(
        BookDetailsQuery,
        db=db,
        label_resolution_service=label_resolution_service,
    )
    note_query = providers.Factory(NoteQuery, db=db)
    book_flashcard_query = providers.Factory(
        BookFlashcardQuery,
        db=db,
        label_resolution_service=label_resolution_service,
    )

    # Learning repositories
    ai_chat_session_repository = providers.Factory(AIChatSessionRepository, db=db)

    # Jobs
    job_batch_repository = providers.Factory(JobBatchRepository, db=db)
    job_batch_query = providers.Factory(JobBatchQuery, db=db)
