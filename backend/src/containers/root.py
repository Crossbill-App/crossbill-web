from dependency_injector import containers, providers

from src.config import get_settings
from src.containers.identity import IdentityContainer
from src.containers.jobs import JobsContainer
from src.containers.learning import LearningContainer
from src.containers.library import LibraryContainer
from src.containers.notes import NotesContainer
from src.containers.reading import ReadingContainer
from src.containers.reflection import ReflectionContainer
from src.containers.shared import SharedContainer
from src.containers.tagging import TaggingContainer
from src.database import current_db_session


class RootContainer(containers.DeclarativeContainer):
    """Root DI container composing module sub-containers."""

    # Resolved per call from the context-bound session rather than overridden on
    # this process-wide container: an override is visible to every concurrent
    # request, so two in flight at once could resolve each other's session.
    db = providers.Callable(current_db_session)

    settings = providers.Object(get_settings())

    shared = providers.Container(SharedContainer, db=db, settings=settings)

    identity = providers.Container(
        IdentityContainer,
        user_repository=shared.user_repository,
        password_service=shared.password_service,
        token_service=shared.token_service,
        refresh_token_repository=shared.refresh_token_repository,
    )

    reading = providers.Container(
        ReadingContainer,
        book_repository=shared.book_repository,
        bookmark_repository=shared.bookmark_repository,
        highlight_repository=shared.highlight_repository,
        tag_repository=shared.tag_repository,
        chapter_repository=shared.chapter_repository,
        reading_session_repository=shared.reading_session_repository,
        chapter_prereading_repository=shared.chapter_prereading_repository,
        highlight_style_repository=shared.highlight_style_repository,
        file_repository=shared.file_repository,
        highlight_deduplication_service=shared.highlight_deduplication_service,
        label_resolution_service=shared.label_resolution_service,
        epub_position_index_service=shared.epub_position_index_service,
        ebook_text_extraction_service=shared.ebook_text_extraction_service,
        ai_service=shared.ai_service,
    )

    tagging = providers.Container(
        TaggingContainer,
        tag_repository=shared.tag_repository,
        book_repository=shared.book_repository,
    )

    library = providers.Container(
        LibraryContainer,
        book_repository=shared.book_repository,
        chapter_repository=shared.chapter_repository,
        highlight_repository=shared.highlight_repository,
        reading_session_repository=shared.reading_session_repository,
        file_repository=shared.file_repository,
        epub_parser_service=shared.epub_parser_service,
        epub_position_index_service=shared.epub_position_index_service,
        cover_image_service=shared.cover_image_service,
        book_details_query=shared.book_details_query,
    )

    learning = providers.Container(
        LearningContainer,
        flashcard_repository=shared.flashcard_repository,
        highlight_repository=shared.highlight_repository,
        label_resolution_service=shared.label_resolution_service,
        book_repository=shared.book_repository,
        chapter_repository=shared.chapter_repository,
        chapter_prereading_repository=shared.chapter_prereading_repository,
        file_repository=shared.file_repository,
        ebook_text_extraction_service=shared.ebook_text_extraction_service,
        ai_service=shared.ai_service,
        ai_chat_session_repository=shared.ai_chat_session_repository,
        note_repository=shared.note_repository,
    )

    notes = providers.Container(
        NotesContainer,
        note_repository=shared.note_repository,
        book_repository=shared.book_repository,
        chapter_repository=shared.chapter_repository,
        highlight_repository=shared.highlight_repository,
        tag_repository=shared.tag_repository,
        flashcard_repository=shared.flashcard_repository,
    )

    reflection = providers.Container(
        ReflectionContainer,
        book_reflection_repository=shared.book_reflection_repository,
        book_repository=shared.book_repository,
        note_repository=shared.note_repository,
    )

    job_queue_service = providers.Dependency()

    jobs = providers.Container(
        JobsContainer,
        job_batch_repository=shared.job_batch_repository,
        job_batch_query=shared.job_batch_query,
        job_queue_service=job_queue_service,
        chapter_repository=shared.chapter_repository,
        book_repository=shared.book_repository,
        chapter_prereading_repository=shared.chapter_prereading_repository,
    )
