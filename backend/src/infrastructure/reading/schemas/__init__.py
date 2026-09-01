"""Reading context schemas."""

from src.infrastructure.common.schemas.position_schemas import PositionResponse
from src.infrastructure.reading.schemas.book_statistics_schemas import (
    BookActivity,
    BookActivityDay,
    BookReadingStatistics,
)
from src.infrastructure.reading.schemas.bookmark_schemas import (
    Bookmark,
    BookmarkBase,
    BookmarkCreateRequest,
)
from src.infrastructure.reading.schemas.highlight_schemas import (
    BookDetails,
    BookHighlightSearchResponse,
    ChapterWithHighlights,
    Highlight,
    HighlightBase,
    HighlightCreate,
    HighlightDeleteRequest,
    HighlightDeleteResponse,
    HighlightLabel,
    HighlightLabelCreate,
    HighlightLabelInBook,
    HighlightLabelUpdate,
    HighlightResponseBase,
    HighlightSyncRequest,
    HighlightSyncResponse,
)
from src.infrastructure.reading.schemas.library_reading_activity_schemas import (
    ActivityBook,
    LibraryActivity,
    LibraryActivityDay,
    LibraryReadingActivityResponse,
    LibraryStats,
)
from src.infrastructure.reading.schemas.reading_session_schemas import (
    ReadingSession,
    ReadingSessionSyncItem,
    ReadingSessionSyncRequest,
    ReadingSessionSyncResponse,
)
from src.infrastructure.reading.schemas.recent_capture_schemas import RecentCapture

__all__ = [
    "ActivityBook",
    "BookActivity",
    "BookActivityDay",
    "BookDetails",
    "BookHighlightSearchResponse",
    "BookReadingStatistics",
    "Bookmark",
    "BookmarkBase",
    "BookmarkCreateRequest",
    "ChapterWithHighlights",
    "Highlight",
    "HighlightBase",
    "HighlightCreate",
    "HighlightDeleteRequest",
    "HighlightDeleteResponse",
    "HighlightLabel",
    "HighlightLabelCreate",
    "HighlightLabelInBook",
    "HighlightLabelUpdate",
    "HighlightResponseBase",
    "HighlightSyncRequest",
    "HighlightSyncResponse",
    "LibraryActivity",
    "LibraryActivityDay",
    "LibraryReadingActivityResponse",
    "LibraryStats",
    "PositionResponse",
    "ReadingSession",
    "ReadingSessionSyncItem",
    "ReadingSessionSyncRequest",
    "ReadingSessionSyncResponse",
    "RecentCapture",
]
