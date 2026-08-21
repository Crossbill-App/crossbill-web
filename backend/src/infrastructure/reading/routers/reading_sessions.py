"""API routes for reading sessions management."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from src.application.reading.commands.reading_sessions.reading_session_ai_summary_use_case import (
    ReadingSessionAISummaryUseCase,
)
from src.application.reading.commands.reading_sessions.reading_session_upload_use_case import (
    ReadingSessionUploadData,
    ReadingSessionUploadUseCase,
)
from src.application.reading.queries.get_book_reading_sessions_use_case import (
    ReadingSessionQueryUseCase,
)
from src.application.reading.queries.reading_sessions import ReadingSessionView
from src.core import container
from src.domain.identity.entities.user import User
from src.infrastructure.common.dependencies import require_ai_enabled
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.common.schemas import PaginatedResponse
from src.infrastructure.identity.dependencies import get_current_user
from src.infrastructure.reading.schemas import (
    Highlight,
    HighlightLabel,
    ReadingSession,
    ReadingSessionAISummaryResponse,
    ReadingSessionUploadRequest,
    ReadingSessionUploadResponse,
)

router = APIRouter(prefix="", tags=["reading_sessions"])


def _build_session_schema(view: ReadingSessionView) -> ReadingSession:
    """Build the ReadingSession schema from the session-list read model.

    A session's highlights are rendered without their chapter, tags or
    flashcards; this list has never loaded them.
    """
    return ReadingSession(
        id=view.id,
        book_id=view.book_id,
        device_id=view.device_id,
        content_hash=view.content_hash,
        start_time=view.start_time,
        end_time=view.end_time,
        start_page=view.start_page,
        end_page=view.end_page,
        content=view.content,
        ai_summary=view.ai_summary,
        created_at=view.created_at,
        highlights=[
            Highlight(
                id=highlight.id,
                book_id=highlight.book_id,
                chapter_id=highlight.chapter_id,
                text=highlight.text,
                page=highlight.page,
                datetime=highlight.datetime,
                created_at=highlight.created_at,
                updated_at=highlight.updated_at,
                label=HighlightLabel(
                    highlight_style_id=highlight.label.highlight_style_id,
                    text=highlight.label.text,
                    ui_color=highlight.label.ui_color,
                )
                if highlight.label
                else None,
                removed_from_devices=highlight.removed_from_devices,
                chapter=None,
                chapter_number=None,
                tags=[],
                flashcards=[],
            )
            for highlight in view.highlights
        ],
    )


@router.post(
    "/reading_sessions/upload",
    response_model=ReadingSessionUploadResponse,
    status_code=status.HTTP_200_OK,
)
async def upload_reading_sessions(
    request: ReadingSessionUploadRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: ReadingSessionUploadUseCase = Depends(
        inject_use_case(container.reading.reading_session_upload_use_case)
    ),
) -> ReadingSessionUploadResponse:
    """
    Upload reading sessions from KOReader for a single book.

    All sessions in a request must be for the same book.

    Args:
        request: Upload request containing book metadata and reading sessions

    Returns:
        ReadingSessionUploadResponse with upload statistics
    """
    # Convert Pydantic schemas to DTOs
    upload_data = [
        ReadingSessionUploadData(
            start_time=s.start_time,
            end_time=s.end_time,
            start_xpoint=s.start_xpoint,
            end_xpoint=s.end_xpoint,
            start_page=s.start_page,
            end_page=s.end_page,
            device_id=s.device_id,
        )
        for s in request.sessions
    ]

    # Call use case
    result = await use_case.upload_reading_sessions(
        client_book_id=request.client_book_id,
        sessions=upload_data,
        user_id=current_user.id.value,
    )

    # Build Pydantic response
    message_parts = []
    if result.created_count > 0:
        message_parts.append(
            f"Created {result.created_count} session{'s' if result.created_count != 1 else ''}"
        )
    if result.skipped_duplicate_count > 0:
        message_parts.append(f"{result.skipped_duplicate_count} skipped (duplicate)")

    message = ". ".join(message_parts) + "." if message_parts else "No sessions to process"

    return ReadingSessionUploadResponse(
        success=True,
        message=message,
        book_id=result.book_id.value,  # Extract .value from BookId
        created_count=result.created_count,
        skipped_duplicate_count=result.skipped_duplicate_count,
    )


@router.get(
    "/books/{book_id}/reading_sessions",
    response_model=PaginatedResponse[ReadingSession],
    status_code=status.HTTP_200_OK,
)
async def get_book_reading_sessions(
    book_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(30, ge=1, le=1000, description="Maximum sessions to return"),
    offset: int = Query(0, ge=0, description="Number of sessions to skip"),
    use_case: ReadingSessionQueryUseCase = Depends(
        inject_use_case(container.reading.reading_session_query_use_case)
    ),
) -> PaginatedResponse[ReadingSession]:
    """
    Get reading sessions for a specific book.

    Returns reading sessions ordered by start time (newest first).

    Args:
        book_id: ID of the book
        limit: Maximum number of sessions
        offset: Pagination offset

    Returns:
        PaginatedResponse with sessions list
    """
    page = await use_case.get_sessions_for_book(
        book_id=book_id,
        user_id=current_user.id.value,
        limit=limit,
        offset=offset,
    )

    return PaginatedResponse[ReadingSession](
        items=[_build_session_schema(view) for view in page.sessions],
        total=page.total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/{reading_session_id}/ai_summary",
    response_model=ReadingSessionAISummaryResponse,
    status_code=status.HTTP_200_OK,
)
@require_ai_enabled
async def get_reading_session_ai_summary(
    reading_session_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: ReadingSessionAISummaryUseCase = Depends(
        inject_use_case(container.reading.reading_session_ai_summary_use_case)
    ),
) -> ReadingSessionAISummaryResponse:
    """
    Get AI-generated summary for a reading session.

    Returns cached summary if available, otherwise generates new summary
    from the read content and caches it.

    Args:
        reading_session_id: ID of the reading session
        current_user: Authenticated user

    Returns:
        ReadingSessionAISummaryResponse with the AI summary

    Raises:
        HTTPException 404: If reading session not found or not owned by user
        HTTPException 400: If session has no position data
        HTTPException 500: For unexpected errors
    """

    summary = await use_case.get_or_generate_summary(reading_session_id, current_user.id.value)
    return ReadingSessionAISummaryResponse(summary=summary)
