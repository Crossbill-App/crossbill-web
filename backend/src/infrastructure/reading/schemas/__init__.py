"""Reading context schemas."""

from src.infrastructure.common.schemas.position_schemas import PositionResponse
from src.infrastructure.reading.schemas.book_statistics_schemas import (
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
from src.infrastructure.reading.schemas.reading_session_schemas import (
    ReadingSession,
    ReadingSessionSyncItem,
    ReadingSessionSyncRequest,
    ReadingSessionSyncResponse,
)

__all__ = [
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
    "PositionResponse",
    "ReadingSession",
    "ReadingSessionSyncItem",
    "ReadingSessionSyncRequest",
    "ReadingSessionSyncResponse",
]
