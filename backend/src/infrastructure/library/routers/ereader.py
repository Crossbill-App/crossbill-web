"""API routes for ereader operations."""

from contextlib import suppress
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from src.application.library.commands.book_management.create_book_from_epub_use_case import (
    CreateBookFromEpubUseCase,
)
from src.application.library.queries.get_ereader_metadata_use_case import (
    EreaderMetadata,
    GetEreaderMetadataUseCase,
)
from src.application.reading.queries.get_ereader_book_digests_use_case import (
    GetEreaderBookDigestsUseCase,
)
from src.application.reading.queries.get_ereader_book_highlights_use_case import (
    GetEreaderBookHighlightsUseCase,
)
from src.core import container
from src.domain.common.value_objects.ids import UserId
from src.domain.identity.entities.user import User
from src.domain.library.exceptions import BookAlreadyExistsError
from src.infrastructure.common.client_version import (
    UPGRADE_REQUIRED_RESPONSES,
    require_koreader_plugin,
)
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.common.schemas import CollectionResponse
from src.infrastructure.identity.dependencies import get_current_user
from src.infrastructure.library.routers.epub_upload import read_epub_upload
from src.infrastructure.library.schemas import EreaderBookMetadata
from src.infrastructure.reading.schemas.chapter_digest_schemas import (
    EreaderChapterDigestItem,
)
from src.infrastructure.reading.schemas.ereader_highlight_schemas import (
    EreaderHighlightItem,
)

# Every route here is called by the KOReader plugin alone, hence a router-wide gate.
router = APIRouter(
    prefix="/ereader",
    tags=["ereader"],
    dependencies=[Depends(require_koreader_plugin)],
    responses=UPGRADE_REQUIRED_RESPONSES,
)


def _metadata_schema(metadata: EreaderMetadata) -> EreaderBookMetadata:
    return EreaderBookMetadata(
        book_id=metadata.book_id,
        bookname=metadata.title,
        author=metadata.author,
        cover_file=metadata.cover_file,
        cover_blurhash=metadata.cover_blurhash,
        has_ebook=metadata.has_ebook,
    )


@router.post(
    "/books",
    response_model=EreaderBookMetadata,
    status_code=status.HTTP_200_OK,
)
async def upload_book(
    epub: Annotated[UploadFile, File(...)],
    client_book_id: Annotated[str, Form(min_length=1, max_length=255)],
    current_user: Annotated[User, Depends(get_current_user)],
    page_count: Annotated[int | None, Form(ge=1)] = None,
    create_use_case: CreateBookFromEpubUseCase = Depends(
        inject_use_case(container.library.create_book_from_epub_use_case)
    ),
    metadata_use_case: GetEreaderMetadataUseCase = Depends(
        inject_use_case(container.library.get_ereader_metadata_use_case)
    ),
) -> EreaderBookMetadata:
    """Create a book from its EPUB under the device's client_book_id, in one call.

    Title, author and language come from the file. A book that already has its
    file is left as it is, and its metadata is returned all the same.
    """
    content = read_epub_upload(epub)
    with suppress(BookAlreadyExistsError):
        await create_use_case.create_book_from_epub(
            content,
            epub.filename,
            current_user.id,
            client_book_id=client_book_id,
            page_count=page_count,
        )

    metadata = await metadata_use_case.get_metadata_for_ereader(
        client_book_id, current_user.id.value
    )
    return _metadata_schema(metadata)


@router.get(
    "/books/{client_book_id}",
    response_model=EreaderBookMetadata,
    status_code=status.HTTP_200_OK,
)
async def get_book_metadata(
    client_book_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: GetEreaderMetadataUseCase = Depends(
        inject_use_case(container.library.get_ereader_metadata_use_case)
    ),
) -> EreaderBookMetadata:
    """
    Get basic book metadata by client_book_id for ereader operations.

    This endpoint returns lightweight book information that KOReader uses to
    decide whether it needs to upload cover images, epub files, etc.

    Args:
        client_book_id: The client-provided stable book identifier
        current_user: Authenticated user

    Returns:
        EreaderBookMetadata with book_id, bookname, author, coverFile, hasEpub

    Raises:
        HTTPException: 404 if book is not found
    """
    metadata = await use_case.get_metadata_for_ereader(client_book_id, current_user.id.value)
    return _metadata_schema(metadata)


@router.get(
    "/books/{client_book_id}/digest",
    response_model=CollectionResponse[EreaderChapterDigestItem],
    status_code=status.HTTP_200_OK,
)
async def get_ereader_book_digest(
    client_book_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: GetEreaderBookDigestsUseCase = Depends(
        inject_use_case(container.reading.get_ereader_book_digests_use_case)
    ),
) -> CollectionResponse[EreaderChapterDigestItem]:
    """
    Get every chapter digest for a book by client_book_id.

    Returns one item per chapter that has a generated digest, ordered
    by the server-side chapter number. Questions are exposed as plain strings
    only (no AI or user answers). A book with no digest yields an empty list.

    Args:
        client_book_id: The client-provided stable book identifier
        current_user: Authenticated user

    Returns:
        CollectionResponse with one item per chapter that has a digest

    Raises:
        HTTPException: 404 if the book is not found for the given client_book_id
    """
    items = await use_case.get_digests_for_client_book(
        client_book_id, UserId(current_user.id.value)
    )
    return CollectionResponse[EreaderChapterDigestItem](
        items=[
            EreaderChapterDigestItem(
                chapter_id=item.chapter_id,
                chapter_name=item.chapter_name,
                chapter_number=item.chapter_number,
                parent_chapter_name=item.parent_chapter_name,
                summary=item.summary,
                keypoints=list(item.keypoints),
                questions=list(item.questions),
                generated_at=item.generated_at,
            )
            for item in items
        ]
    )


@router.get(
    "/books/{client_book_id}/highlights",
    response_model=CollectionResponse[EreaderHighlightItem],
    status_code=status.HTTP_200_OK,
)
async def get_ereader_book_highlights(
    client_book_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: GetEreaderBookHighlightsUseCase = Depends(
        inject_use_case(container.reading.get_ereader_book_highlights_use_case)
    ),
) -> CollectionResponse[EreaderHighlightItem]:
    """
    Get every highlight of a book by client_book_id.

    The server is the master copy: this returns all live highlights of the book,
    including ones made on other devices and ones the device has already seen.
    Deleted highlights are omitted, so a device that removes what it cannot find
    here converges on the server's set. Highlights without both xpoints cannot be
    placed in the book and say so via `placeable`.

    Args:
        client_book_id: The client-provided stable book identifier
        current_user: Authenticated user

    Returns:
        CollectionResponse with one item per live highlight

    Raises:
        HTTPException: 404 if the book is not found for the given client_book_id
    """
    items = await use_case.get_highlights_for_client_book(
        client_book_id, UserId(current_user.id.value)
    )
    return CollectionResponse[EreaderHighlightItem](
        items=[
            EreaderHighlightItem(
                id=item.id,
                text=item.text,
                start_xpoint=item.start_xpoint,
                end_xpoint=item.end_xpoint,
                datetime=item.datetime,
                datetime_updated=item.datetime_updated,
                page=item.page,
                chapter_number=item.chapter_number,
                chapter_name=item.chapter_name,
                device_color=item.device_color,
                device_style=item.device_style,
                note=item.note,
                origin_device_id=item.origin_device_id,
                placeable=item.placeable,
            )
            for item in items
        ]
    )
