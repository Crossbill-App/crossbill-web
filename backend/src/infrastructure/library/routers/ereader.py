"""API routes for ereader operations."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status

from src.application.library.dtos import CreateBookInput
from src.application.library.use_cases.book_files.ebook_upload_use_case import EbookUploadUseCase
from src.application.library.use_cases.book_management.create_book_use_case import (
    CreateBookUseCase,
)
from src.application.library.use_cases.book_queries.get_ereader_metadata_use_case import (
    GetEreaderMetadataUseCase,
)
from src.application.reading.use_cases.chapter_prereading.get_ereader_book_prereading_use_case import (
    GetEreaderBookPrereadingUseCase,
)
from src.core import container
from src.domain.common.exceptions import ValidationError
from src.domain.common.value_objects.ids import UserId
from src.domain.identity.entities.user import User
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.common.schemas import CollectionResponse, SuccessResponse
from src.infrastructure.identity.dependencies import get_current_user
from src.infrastructure.library.schemas import (
    BookCreate,
    EreaderBookMetadata,
)
from src.infrastructure.reading.schemas.chapter_prereading_schemas import (
    EreaderChapterPrereadingItem,
)

router = APIRouter(prefix="/ereader", tags=["ereader"])


@router.post(
    "/books",
    response_model=EreaderBookMetadata,
    status_code=status.HTTP_200_OK,
)
async def create_book(
    book_data: BookCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    create_use_case: CreateBookUseCase = Depends(
        inject_use_case(container.library.create_book_use_case)
    ),
    metadata_use_case: GetEreaderMetadataUseCase = Depends(
        inject_use_case(container.library.get_ereader_metadata_use_case)
    ),
) -> EreaderBookMetadata:
    """
    Create or get a book by client_book_id.

    This endpoint creates a new book if it doesn't exist, or returns the existing
    book's metadata if it does. Used by KOReader to ensure a book exists before
    uploading highlights, covers, or EPUB files.

    Args:
        book_data: Book creation data (same format as highlight upload)
        current_user: Authenticated user

    Returns:
        EreaderBookMetadata with book_id, bookname, author, cover_file, has_epub
    """
    create_input = CreateBookInput(
        title=book_data.title,
        client_book_id=book_data.client_book_id,
        author=book_data.author,
        isbn=book_data.isbn,
        description=book_data.description,
        language=book_data.language,
        page_count=book_data.page_count,
    )
    await create_use_case.create_book(create_input, current_user.id.value)

    metadata = await metadata_use_case.get_metadata_for_ereader(
        book_data.client_book_id, current_user.id.value
    )
    return EreaderBookMetadata(
        book_id=metadata.book_id,
        bookname=metadata.title,
        author=metadata.author,
        cover_file=metadata.cover_file,
        cover_blurhash=metadata.cover_blurhash,
        has_ebook=metadata.has_ebook,
    )


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
    return EreaderBookMetadata(
        book_id=metadata.book_id,
        bookname=metadata.title,
        author=metadata.author,
        cover_file=metadata.cover_file,
        cover_blurhash=metadata.cover_blurhash,
        has_ebook=metadata.has_ebook,
    )


# Maximum ebook file size (50MB - epubs and PDFs can be large)
MAX_EBOOK_SIZE = 50 * 1024 * 1024


@router.post(
    "/books/{client_book_id}/epub",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
)
async def upload_book_epub(
    client_book_id: str,
    epub: Annotated[UploadFile, File(...)],
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: EbookUploadUseCase = Depends(
        inject_use_case(container.library.ebook_upload_use_case)
    ),
) -> SuccessResponse:
    """
    Upload an ebook file (EPUB) for a book using client_book_id.

    This endpoint accepts an uploaded ebook file and saves it for the book.
    Used by KOReader which identifies books by client_book_id.

    Args:
        client_book_id: The client-provided stable book identifier
        epub: Uploaded ebook file (EPUB or PDF)
        current_user: Authenticated user

    Returns:
        SuccessResponse with success status

    Raises:
        HTTPException: 400 for invalid file, 404 if book is not found
    """
    # Validate content-type
    allowed_types = {"application/epub+zip"}
    if epub.content_type not in allowed_types:
        raise ValidationError("Only EPUB and PDF files are allowed")

    # Read file with size limit
    content = epub.file.read(MAX_EBOOK_SIZE + 1)
    if len(content) > MAX_EBOOK_SIZE:
        raise ValidationError(f"File too large (max {MAX_EBOOK_SIZE // (1024 * 1024)}MB)")

    await use_case.upload_ebook(
        client_book_id, content, epub.content_type or "", current_user.id.value
    )

    return SuccessResponse(
        success=True,
        message="Ebook uploaded successfully",
    )


@router.get(
    "/books/{client_book_id}/prereading",
    response_model=CollectionResponse[EreaderChapterPrereadingItem],
    status_code=status.HTTP_200_OK,
)
async def get_ereader_book_prereading(
    client_book_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: GetEreaderBookPrereadingUseCase = Depends(
        inject_use_case(container.reading.get_ereader_book_prereading_use_case)
    ),
) -> CollectionResponse[EreaderChapterPrereadingItem]:
    """
    Get all chapter prereading content for a book by client_book_id.

    Returns one item per chapter that has generated prereading content, ordered
    by the server-side chapter number. Questions are exposed as plain strings
    only (no AI or user answers). A book with no prereading yields an empty list.

    Args:
        client_book_id: The client-provided stable book identifier
        current_user: Authenticated user

    Returns:
        CollectionResponse with one item per chapter that has prereading

    Raises:
        HTTPException: 404 if the book is not found for the given client_book_id
    """
    items = await use_case.get_prereading_for_client_book(
        client_book_id, UserId(current_user.id.value)
    )
    return CollectionResponse[EreaderChapterPrereadingItem](
        items=[
            EreaderChapterPrereadingItem(
                chapter_id=item.chapter_id,
                chapter_name=item.chapter_name,
                chapter_number=item.chapter_number,
                parent_chapter_name=item.parent_chapter_name,
                summary=item.summary,
                keypoints=item.keypoints,
                questions=item.questions,
                generated_at=item.generated_at,
            )
            for item in items
        ]
    )
