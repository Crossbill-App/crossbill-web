"""API routes for highlights management."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from src.application.reading.commands.highlights.highlight_delete_use_case import (
    HighlightDeleteUseCase,
)
from src.application.reading.commands.highlights.highlight_upload_use_case import (
    HighlightUploadData,
    HighlightUploadUseCase,
)
from src.application.reading.queries.highlight_search import (
    BookHighlightSearchView,
    SearchChapterView,
)
from src.application.reading.queries.highlight_search_use_case import (
    HighlightSearchUseCase,
)
from src.application.web_reader.queries.get_highlight_locators_use_case import (
    GetHighlightLocatorsUseCase,
)
from src.application.web_reader.queries.highlight_locators import DerivedHighlightLocator
from src.core import container
from src.domain.common.value_objects.ids import BookId
from src.domain.identity.entities.user import User
from src.infrastructure.common.client_version import (
    UPGRADE_REQUIRED_RESPONSES,
    require_koreader_plugin,
)
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.identity.dependencies import get_current_user
from src.infrastructure.reading.schemas import (
    BookHighlightSearchResponse,
    ChapterWithHighlights,
    HighlightDeleteRequest,
    HighlightDeleteResponse,
    HighlightSyncRequest,
    HighlightSyncResponse,
)
from src.infrastructure.reading.schemas.highlight_builders import (
    build_highlight_schema,
    resolve_locator,
)

router = APIRouter(prefix="", tags=["highlights"])


LOCATOR_INCLUDE = "locator"


def _matched_ids(view: BookHighlightSearchView) -> list[int]:
    """The highlights this response will render, so only they are placed.

    A search shows a handful of a book's highlights, and deriving a locator
    costs per highlight rather than per book (ADR-0004 §4) -- so a heavily
    annotated book searched for one word must not pay for its whole list.
    """
    return [highlight.id for chapter in view.chapters for highlight in chapter.highlights]


def _build_chapter_schema(
    chapter: SearchChapterView,
    locators: dict[int, DerivedHighlightLocator],
    wanted: bool,
) -> ChapterWithHighlights:
    """Build the ChapterWithHighlights schema from the search read model.

    Search rows carry no parent chapter or start position, and never have.
    ``wanted`` says whether the caller asked for locators at all, which is what
    separates "no locator was requested" from "this one could not be placed".
    """
    return ChapterWithHighlights(
        id=chapter.id,
        name=chapter.name,
        chapter_number=chapter.chapter_number,
        parent_id=None,
        start_position=None,
        highlights=[
            build_highlight_schema(highlight, resolve_locator(highlight.id, locators, wanted))
            for highlight in chapter.highlights
        ],
        created_at=chapter.created_at,
        updated_at=chapter.updated_at,
    )


# Gated per route: only the KOReader plugin syncs, the rest serves the web app.
@router.post(
    "/highlights/sync",
    response_model=HighlightSyncResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_koreader_plugin)],
    responses=UPGRADE_REQUIRED_RESPONSES,
)
# The path this endpoint was born under, kept until plugins calling it are gone.
@router.post(
    "/highlights/upload",
    operation_id="upload_highlights",
    response_model=HighlightSyncResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_koreader_plugin)],
    responses=UPGRADE_REQUIRED_RESPONSES,
    deprecated=True,
)
async def sync_highlights(
    request: HighlightSyncRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: HighlightUploadUseCase = Depends(
        inject_use_case(container.reading.highlight_upload_use_case)
    ),
) -> HighlightSyncResponse:
    """
    Sync highlights from KOReader.

    Creates or updates book record and adds highlights with automatic deduplication.
    Duplicates are identified by book and highlighted text alone: a highlight's
    timestamps say when the device made and edited it, and take no part in
    deciding whether it is the same highlight.

    ``removed_ids`` carries the highlights the reader deleted on the device:
    they are withheld from every device's pull and stay whole on the web.

    A highlight flagged ``is_new`` was created on the device after its last
    pull, so a duplicate of a removed or deleted highlight is a deliberate
    re-highlight and brings that highlight back.

    Args:
        request: Highlight sync request containing book metadata and highlights

    Returns:
        HighlightSyncResponse with sync statistics

    Raises:
        HTTPException: If the sync fails due to server error
    """
    highlight_data_list = [
        HighlightUploadData(
            text=h.text,
            chapter_number=h.chapter_number,
            chapter=h.chapter,
            start_xpoint=h.start_xpoint,
            end_xpoint=h.end_xpoint,
            page=h.page,
            color=h.color,
            drawer=h.drawer,
            datetime=h.datetime,
            datetime_updated=h.datetime_updated,
            koreader_note=h.note,
            is_new=h.is_new,
        )
        for h in request.highlights
    ]

    result = await use_case.upload_highlights(
        client_book_id=request.client_book_id,
        highlight_data_list=highlight_data_list,
        user_id=current_user.id.value,
        device_id=request.device_id,
        removed_ids=request.removed_ids,
    )

    return HighlightSyncResponse(
        success=True,
        message="Successfully synced highlights",
        book_id=0,  # TODO: Return actual book_id from service if needed
        highlights_created=result.created,
        highlights_skipped=result.skipped,
        highlights_removed=result.removed_from_devices,
    )


@router.get(
    "/books/{book_id}/highlights",
    response_model=BookHighlightSearchResponse,
    status_code=status.HTTP_200_OK,
)
async def search_book_highlights(
    book_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    search_text: str = Query(
        ...,
        alias="searchText",
        min_length=1,
        description="Text to search for in highlights",
    ),
    include: Annotated[
        list[str] | None,
        Query(
            description=(
                "Optional extras to compute for each highlight. `locator` adds the "
                "Readium locator the web reader draws and jumps by, derived from the "
                "highlight's stored position against the book's EPUB. Off by default "
                "because it costs an EPUB parse, which a list that renders no "
                "decorations has no use for."
            ),
        ),
    ] = None,
    use_case: HighlightSearchUseCase = Depends(
        inject_use_case(container.reading.highlight_search_use_case)
    ),
    locator_use_case: GetHighlightLocatorsUseCase = Depends(
        inject_use_case(container.web_reader.get_highlight_locators_use_case)
    ),
) -> BookHighlightSearchResponse:
    """
    Search for highlights in book using full-text search.

    Searches across all highlight text using PostgreSQL full-text search.
    Results are ranked by relevance and excludes soft-deleted highlights.
    """
    view = await use_case.search_book_highlights(book_id, current_user.id.value, search_text)
    wanted = LOCATOR_INCLUDE in (include or ())
    locators = (
        await locator_use_case.for_book(BookId(book_id), current_user.id, _matched_ids(view))
        if wanted
        else {}
    )
    return BookHighlightSearchResponse(
        chapters=[_build_chapter_schema(chapter, locators, wanted) for chapter in view.chapters],
        total=view.total,
    )


@router.delete(
    "/books/{book_id}/highlight",
    response_model=HighlightDeleteResponse,
    status_code=status.HTTP_200_OK,
)
async def delete_highlights(
    book_id: int,
    request: HighlightDeleteRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: HighlightDeleteUseCase = Depends(
        inject_use_case(container.reading.highlight_delete_use_case)
    ),
) -> HighlightDeleteResponse:
    """
    Soft delete highlights from a book.

    This performs a soft delete by marking the highlights as deleted.
    When syncing highlights, deleted highlights will not be recreated,
    ensuring that user deletions persist across syncs.

    Args:
        book_id: ID of the book
        request: Request containing list of highlight IDs to delete

    Returns:
        HighlightDeleteResponse with deletion status and count

    Raises:
        HTTPException: If book is not found or deletion fails
        :param use_case:
    """
    deleted_count = await use_case.delete_highlights(
        book_id, request.highlight_ids, current_user.id.value
    )
    return HighlightDeleteResponse(
        success=True,
        message=f"Successfully deleted {deleted_count} highlight(s)",
        deleted_count=deleted_count,
    )
