"""Static protocol-conformance checks. Nothing here runs.

Pyright type-checks this module, so a concrete repository drifting out of its
protocol (a renamed parameter, a changed return type) fails `uv run pyright`
immediately instead of surfacing in whichever test first passes the concrete
class to a typed constructor. Pytest does not collect this file (no `test_`
prefix). When adding a repository or query adapter, add its pair here.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from src.application.identity.protocols.refresh_token_repository import (
    RefreshTokenRepositoryProtocol,
)
from src.application.identity.protocols.user_repository import UserRepositoryProtocol
from src.application.jobs.protocols.job_batch_repository import JobBatchRepositoryProtocol
from src.application.jobs.queries.job_batch import JobBatchQueryProtocol
from src.application.learning.protocols.ai_chat_session_repository import (
    AIChatSessionRepositoryProtocol,
)
from src.application.learning.protocols.flashcard_repository import FlashcardRepositoryProtocol
from src.application.learning.queries.book_flashcards import BookFlashcardQueryProtocol
from src.application.library.protocols.book_repository import (
    BookRepositoryProtocol as LibraryBookRepositoryProtocol,
)
from src.application.library.protocols.chapter_repository import ChapterRepositoryProtocol
from src.application.library.protocols.file_repository import FileRepositoryProtocol
from src.application.library.queries.book_details import BookDetailsQueryProtocol
from src.application.library.queries.book_list import BookListQueryProtocol
from src.application.notes.protocols.note_repository import NoteRepositoryProtocol
from src.application.notes.queries.note_with_links import NoteQueryProtocol
from src.application.reading.protocols.book_repository import (
    BookRepositoryProtocol as ReadingBookRepositoryProtocol,
)
from src.application.reading.protocols.bookmark_repository import BookmarkRepositoryProtocol
from src.application.reading.protocols.chapter_prereading_repository import (
    ChapterPrereadingRepositoryProtocol,
)
from src.application.reading.protocols.ebook_text_extraction_service import (
    EbookTextExtractionServiceProtocol,
)
from src.application.reading.protocols.highlight_repository import HighlightRepositoryProtocol
from src.application.reading.protocols.highlight_style_repository import (
    HighlightStyleRepositoryProtocol,
)
from src.application.reading.protocols.reading_session_repository import (
    ReadingSessionRepositoryProtocol,
)
from src.application.reading.queries.bookmarks import BookmarkQueryProtocol
from src.application.reading.queries.highlight_labels import HighlightLabelQueryProtocol
from src.application.reading.queries.highlight_search import HighlightSearchQueryProtocol
from src.application.reading.queries.reading_sessions import ReadingSessionQueryProtocol
from src.application.reading.services.label_resolution_service import LabelResolutionService
from src.application.reflection.protocols.book_reflection_repository import (
    BookReflectionRepositoryProtocol,
)
from src.application.tagging.protocols.tag_repository import TagRepositoryProtocol
from src.infrastructure.identity.repositories.refresh_token_repository import (
    RefreshTokenRepository,
)
from src.infrastructure.identity.repositories.user_repository import UserRepository
from src.infrastructure.jobs.queries.job_batch_query import JobBatchQuery
from src.infrastructure.jobs.repositories.job_batch_repository import JobBatchRepository
from src.infrastructure.learning.queries.book_flashcard_query import BookFlashcardQuery
from src.infrastructure.learning.repositories.ai_chat_session_repository import (
    AIChatSessionRepository,
)
from src.infrastructure.learning.repositories.flashcard_repository import FlashcardRepository
from src.infrastructure.library.queries.book_details_query import BookDetailsQuery
from src.infrastructure.library.queries.book_list_query import BookListQuery
from src.infrastructure.library.repositories import BookRepository
from src.infrastructure.library.repositories.chapter_repository import ChapterRepository
from src.infrastructure.notes.queries.note_query import NoteQuery
from src.infrastructure.notes.repositories.note_repository import NoteRepository
from src.infrastructure.reading.queries.bookmark_query import BookmarkQuery
from src.infrastructure.reading.queries.highlight_label_query import HighlightLabelQuery
from src.infrastructure.reading.queries.highlight_search_query import HighlightSearchQuery
from src.infrastructure.reading.queries.reading_session_query import ReadingSessionQuery
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


def repositories_satisfy_their_protocols(
    db: AsyncSession,
    label_resolution_service: LabelResolutionService,
    file_repository: FileRepositoryProtocol,
    text_extraction_service: EbookTextExtractionServiceProtocol,
) -> None:
    _user: UserRepositoryProtocol = UserRepository(db)
    _refresh_token: RefreshTokenRepositoryProtocol = RefreshTokenRepository(db)
    _book_library: LibraryBookRepositoryProtocol = BookRepository(db)
    _book_reading: ReadingBookRepositoryProtocol = BookRepository(db)
    _chapter: ChapterRepositoryProtocol = ChapterRepository(db)
    _bookmark: BookmarkRepositoryProtocol = BookmarkRepository(db)
    _highlight: HighlightRepositoryProtocol = HighlightRepository(db)
    _highlight_style: HighlightStyleRepositoryProtocol = HighlightStyleRepository(db)
    _reading_session: ReadingSessionRepositoryProtocol = ReadingSessionRepository(db)
    _chapter_prereading: ChapterPrereadingRepositoryProtocol = ChapterPrereadingRepository(db)
    _tag: TagRepositoryProtocol = TagRepository(db)
    _note: NoteRepositoryProtocol = NoteRepository(db)
    _flashcard: FlashcardRepositoryProtocol = FlashcardRepository(db)
    _ai_chat_session: AIChatSessionRepositoryProtocol = AIChatSessionRepository(db)
    _job_batch: JobBatchRepositoryProtocol = JobBatchRepository(db)
    _book_reflection: BookReflectionRepositoryProtocol = BookReflectionRepository(db)
    _book_details: BookDetailsQueryProtocol = BookDetailsQuery(db, label_resolution_service)
    _book_list_view: BookListQueryProtocol = BookListQuery(db)
    _job_batch_view: JobBatchQueryProtocol = JobBatchQuery(db)
    _note_view: NoteQueryProtocol = NoteQuery(db)
    _book_flashcards_view: BookFlashcardQueryProtocol = BookFlashcardQuery(
        db, label_resolution_service
    )
    _bookmarks_view: BookmarkQueryProtocol = BookmarkQuery(db)
    _highlight_labels_view: HighlightLabelQueryProtocol = HighlightLabelQuery(
        db, label_resolution_service
    )
    _highlight_search_view: HighlightSearchQueryProtocol = HighlightSearchQuery(
        db, label_resolution_service
    )
    _reading_sessions_view: ReadingSessionQueryProtocol = ReadingSessionQuery(
        db, label_resolution_service, file_repository, text_extraction_service
    )
