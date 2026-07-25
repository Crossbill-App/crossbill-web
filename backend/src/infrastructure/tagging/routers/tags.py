"""API routes for tags, tag groups and tag-highlight associations."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.application.reading.use_cases.tag_associations.add_tag_to_highlight_by_id_use_case import (
    AddTagToHighlightByIdUseCase,
)
from src.application.reading.use_cases.tag_associations.add_tag_to_highlight_by_name_use_case import (
    AddTagToHighlightByNameUseCase,
)
from src.application.reading.use_cases.tag_associations.remove_tag_from_highlight_use_case import (
    RemoveTagFromHighlightUseCase,
)
from src.application.tagging.use_cases.tag_groups.create_tag_group_use_case import (
    CreateTagGroupUseCase,
)
from src.application.tagging.use_cases.tag_groups.delete_tag_group_use_case import (
    DeleteTagGroupUseCase,
)
from src.application.tagging.use_cases.tag_groups.update_tag_group_association_use_case import (
    UpdateTagGroupAssociationUseCase,
)
from src.application.tagging.use_cases.tag_groups.update_tag_group_use_case import (
    UpdateTagGroupUseCase,
)
from src.application.tagging.use_cases.tags.create_tag_use_case import (
    CreateTagUseCase,
)
from src.application.tagging.use_cases.tags.delete_tag_use_case import (
    DeleteTagUseCase,
)
from src.application.tagging.use_cases.tags.get_tags_for_book_use_case import (
    GetTagsForBookUseCase,
)
from src.application.tagging.use_cases.tags.update_tag_name_use_case import (
    UpdateTagNameUseCase,
)
from src.core import container
from src.database import DatabaseSession
from src.domain.common.exceptions import ValidationError
from src.domain.common.value_objects import TagId, UserId
from src.domain.identity.entities.user import User
from src.domain.tagging.exceptions import TagGroupNotFoundError, TagNotFoundError
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.common.schemas import CollectionResponse
from src.infrastructure.identity.dependencies import get_current_user
from src.infrastructure.learning.schemas import (
    Flashcard,
)
from src.infrastructure.reading.schemas import (
    Highlight,
    HighlightLabel,
)
from src.infrastructure.tagging.repositories import TagRepository
from src.infrastructure.tagging.schemas import (
    Tag,
    TagAssociationRequest,
    TagCreateRequest,
    TagGroup,
    TagGroupCreateRequest,
    TagInBook,
    TagUpdateRequest,
)

router = APIRouter(prefix="", tags=["tags"])


@router.post(
    "/tag-groups",
    response_model=TagGroup,
    status_code=status.HTTP_200_OK,
)
async def create_or_update_tag_group(
    request: TagGroupCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    create_use_case: CreateTagGroupUseCase = Depends(
        inject_use_case(container.tagging.create_tag_group_use_case)
    ),
    update_use_case: UpdateTagGroupUseCase = Depends(
        inject_use_case(container.tagging.update_tag_group_use_case)
    ),
) -> TagGroup:
    """
    Create a new tag group or update an existing one.

    Args:
        request: Tag group creation/update request

    Returns:
        Created or updated TagGroup

    Raises:
        HTTPException: If creation/update fails
    """
    # Create or update based on whether ID is provided
    if request.id is not None:
        # Update existing
        tag_group = await update_use_case.update_group(
            group_id=request.id,
            book_id=request.book_id,
            new_name=request.name,
            user_id=current_user.id.value,
        )
    else:
        # Create new
        tag_group = await create_use_case.create_group(
            book_id=request.book_id,
            name=request.name,
            user_id=current_user.id.value,
        )

    # Manually construct response to handle value objects
    return TagGroup(
        id=tag_group.id.value,
        book_id=tag_group.book_id.value,
        name=tag_group.name,
    )


@router.delete(
    "/tag-groups/{tag_group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_tag_group(
    tag_group_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: DeleteTagGroupUseCase = Depends(
        inject_use_case(container.tagging.delete_tag_group_use_case)
    ),
) -> None:
    """
    Delete a tag group.

    Args:
        tag_group_id: ID of the tag group to delete

    Raises:
        HTTPException: If tag group not found or deletion fails
    """
    success = await use_case.delete_group(tag_group_id, current_user.id.value)
    if not success:
        raise TagGroupNotFoundError(tag_group_id)


@router.get(
    "/books/{book_id}/tags",
    response_model=CollectionResponse[Tag],
    status_code=status.HTTP_200_OK,
)
async def get_tags(
    book_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: GetTagsForBookUseCase = Depends(
        inject_use_case(container.tagging.get_tags_for_book_use_case)
    ),
) -> CollectionResponse[Tag]:
    """
    Get all tags for a book.

    Args:
        book_id: ID of the book

    Returns:
        List of Tags for the book

    Raises:
        HTTPException: If book is not found
    """
    tags = await use_case.get_tags(book_id, current_user.id.value)
    return CollectionResponse[Tag](
        items=[
            Tag(
                id=tag.id.value,
                book_id=tag.book_id.value,
                name=tag.name,
                tag_group_id=tag.tag_group_id,
            )
            for tag in tags
        ]
    )


@router.post(
    "/books/{book_id}/tag",
    response_model=Tag,
    status_code=status.HTTP_201_CREATED,
)
async def create_tag(
    book_id: int,
    request: TagCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: CreateTagUseCase = Depends(inject_use_case(container.tagging.create_tag_use_case)),
) -> Tag:
    """
    Create a new tag for a book.

    Args:
        book_id: ID of the book
        request: Request containing tag name

    Returns:
        Created Tag

    Raises:
        HTTPException: If book is not found, tag already exists, or creation fails
    """
    tag = await use_case.create_tag(book_id, request.name, user_id=current_user.id.value)
    return Tag(
        id=tag.id.value,
        book_id=tag.book_id.value,
        name=tag.name,
        tag_group_id=tag.tag_group_id,
    )


@router.delete(
    "/books/{book_id}/tag/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_tag(
    book_id: int,
    tag_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: DeleteTagUseCase = Depends(inject_use_case(container.tagging.delete_tag_use_case)),
) -> None:
    """
    Delete a tag from a book.

    This will also remove the tag from all highlights it was associated with.

    Args:
        book_id: ID of the book
        tag_id: ID of the tag to delete

    Raises:
        HTTPException: If tag is not found, doesn't belong to book, or deletion fails
    """
    deleted = await use_case.delete_tag(book_id, tag_id, current_user.id.value)
    if not deleted:
        raise TagNotFoundError(tag_id)


@router.post(
    "/books/{book_id}/tag/{tag_id}",
    response_model=Tag,
    status_code=status.HTTP_200_OK,
)
async def update_tag(
    book_id: int,
    tag_id: int,
    request: TagUpdateRequest,
    db: DatabaseSession,
    current_user: Annotated[User, Depends(get_current_user)],
    tag_use_case: UpdateTagNameUseCase = Depends(
        inject_use_case(container.tagging.update_tag_name_use_case)
    ),
    group_use_case: UpdateTagGroupAssociationUseCase = Depends(
        inject_use_case(container.tagging.update_tag_group_association_use_case)
    ),
) -> Tag:
    """
    Update a tag's name and/or tag group association.

    Args:
        book_id: ID of the book
        tag_id: ID of the tag to update
        request: Request containing updated tag information

    Returns:
        Updated Tag

    Raises:
        HTTPException: If tag not found, doesn't belong to book, or update fails
    """
    # Update name if provided
    if request.name is not None:
        tag = await tag_use_case.update_tag_name(
            book_id=book_id,
            tag_id=tag_id,
            new_name=request.name,
            user_id=current_user.id.value,
        )
    else:
        # TODO: Fix this direct repository call. It is apparently done just so that tag is not
        # undefined before we return from this route.
        # Load tag for group update
        tag_repo = TagRepository(db)
        tag = await tag_repo.find_by_id(TagId(tag_id), UserId(current_user.id.value))
        if not tag:
            raise TagNotFoundError(tag_id)

    # Update group association if provided (including None to clear)
    if hasattr(request, "tag_group_id"):
        tag = await group_use_case.update_association(
            book_id=book_id,
            tag_id=tag_id,
            group_id=request.tag_group_id,
            user_id=current_user.id.value,
        )

    return Tag(
        id=tag.id.value,
        book_id=tag.book_id.value,
        name=tag.name,
        tag_group_id=tag.tag_group_id,
    )


@router.post(
    "/books/{book_id}/highlight/{highlight_id}/tag",
    response_model=Highlight,
    status_code=status.HTTP_200_OK,
)
async def add_tag_to_highlight(
    book_id: int,
    highlight_id: int,
    request: TagAssociationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    add_by_id_use_case: AddTagToHighlightByIdUseCase = Depends(
        inject_use_case(container.reading.add_tag_to_highlight_by_id_use_case)
    ),
    add_by_name_use_case: AddTagToHighlightByNameUseCase = Depends(
        inject_use_case(container.reading.add_tag_to_highlight_by_name_use_case)
    ),
) -> Highlight:
    """
    Add a tag to a highlight.

    If a tag name is provided and doesn't exist, it will be created first.
    If a tag_id is provided, it will be used directly.

    Args:
        book_id: ID of the book
        highlight_id: ID of the highlight
        request: Request containing either tag name or tag_id

    Returns:
        Updated Highlight with tags

    Raises:
        HTTPException: If highlight or tag not found, or association fails
    """
    # Add tag by ID or by name (with get_or_create)
    if request.tag_id is not None:
        highlight, flashcards, tags, labels = await add_by_id_use_case.add_tag(
            highlight_id, request.tag_id, current_user.id.value
        )
    elif request.name is not None:
        highlight, flashcards, tags, labels = await add_by_name_use_case.add_tag(
            book_id, highlight_id, request.name, current_user.id.value
        )
    else:
        raise ValidationError("Either tag_id or name must be provided")

    resolved = (
        labels.get(highlight.highlight_style_id.value) if highlight.highlight_style_id else None
    )

    # Manually construct schema from domain entities
    return Highlight(
        id=highlight.id.value,
        book_id=highlight.book_id.value,
        chapter_id=highlight.chapter_id.value if highlight.chapter_id else None,
        text=highlight.text,
        chapter=None,
        chapter_number=None,
        page=highlight.page,
        datetime=highlight.datetime,
        label=HighlightLabel(
            highlight_style_id=highlight.highlight_style_id.value
            if highlight.highlight_style_id
            else None,
            text=resolved.label if resolved else None,
            ui_color=resolved.ui_color if resolved else None,
        )
        if highlight.highlight_style_id
        else None,
        tags=[
            TagInBook(
                id=tag.id.value,
                name=tag.name,
                tag_group_id=tag.tag_group_id,
            )
            for tag in tags
        ],
        flashcards=[
            Flashcard(
                id=fc.id.value,
                user_id=fc.user_id.value,
                book_id=fc.book_id.value,
                highlight_id=fc.highlight_id.value if fc.highlight_id else None,
                question=fc.question,
                answer=fc.answer,
            )
            for fc in flashcards
        ],
        created_at=highlight.created_at,
        updated_at=highlight.updated_at,
    )


@router.delete(
    "/books/{book_id}/highlight/{highlight_id}/tag/{tag_id}",
    response_model=Highlight,
    status_code=status.HTTP_200_OK,
)
async def remove_tag_from_highlight(
    book_id: int,
    highlight_id: int,
    tag_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: RemoveTagFromHighlightUseCase = Depends(
        inject_use_case(container.reading.remove_tag_from_highlight_use_case)
    ),
) -> Highlight:
    """
    Remove a tag from a highlight.

    Args:
        book_id: ID of the book
        highlight_id: ID of the highlight
        tag_id: ID of the tag to remove

    Returns:
        Updated Highlight with tags

    Raises:
        HTTPException: If highlight not found or removal fails
    """
    highlight, flashcards, tags, labels = await use_case.remove_tag(
        highlight_id, tag_id, current_user.id.value
    )

    resolved = (
        labels.get(highlight.highlight_style_id.value) if highlight.highlight_style_id else None
    )

    # Manually construct schema from domain entities
    return Highlight(
        id=highlight.id.value,
        book_id=highlight.book_id.value,
        chapter_id=highlight.chapter_id.value if highlight.chapter_id else None,
        text=highlight.text,
        chapter=None,
        chapter_number=None,
        page=highlight.page,
        datetime=highlight.datetime,
        label=HighlightLabel(
            highlight_style_id=highlight.highlight_style_id.value
            if highlight.highlight_style_id
            else None,
            text=resolved.label if resolved else None,
            ui_color=resolved.ui_color if resolved else None,
        )
        if highlight.highlight_style_id
        else None,
        tags=[
            TagInBook(
                id=tag.id.value,
                name=tag.name,
                tag_group_id=tag.tag_group_id,
            )
            for tag in tags
        ],
        flashcards=[
            Flashcard(
                id=fc.id.value,
                user_id=fc.user_id.value,
                book_id=fc.book_id.value,
                highlight_id=fc.highlight_id.value if fc.highlight_id else None,
                question=fc.question,
                answer=fc.answer,
            )
            for fc in flashcards
        ],
        created_at=highlight.created_at,
        updated_at=highlight.updated_at,
    )
