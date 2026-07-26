"""API routes for note management."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from starlette import status

from src.application.notes.commands.create_note_use_case import CreateNoteUseCase
from src.application.notes.commands.delete_note_use_case import DeleteNoteUseCase
from src.application.notes.commands.update_note_use_case import UpdateNoteUseCase
from src.application.notes.queries.get_note_use_case import GetNoteUseCase
from src.application.notes.queries.get_notes_by_book_use_case import GetNotesByBookUseCase
from src.application.notes.queries.note_with_links import NoteWithLinksView
from src.core import container
from src.domain.identity import User
from src.domain.notes.entities.note import Note as NoteEntity
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.common.schemas import CollectionResponse, SuccessResponse
from src.infrastructure.identity import get_current_user
from src.infrastructure.learning.schemas import Flashcard
from src.infrastructure.notes.schemas import (
    Note,
    NoteCreateRequest,
    NoteCreateResponse,
    NoteKindLiteral,
    NoteLinkedChapter,
    NoteLinkedHighlight,
    NoteLinkedTag,
    NoteUpdateRequest,
    NoteUpdateResponse,
    NoteWithLinks,
)

router = APIRouter(tags=["notes"])

HIGHLIGHT_SNIPPET_LENGTH = 200


def note_entity_to_schema(entity: NoteEntity) -> Note:
    """Convert a Note domain entity to its response schema."""
    return Note(
        id=entity.id.value,
        user_id=entity.user_id.value,
        title=entity.title,
        body=entity.body,
        kind=entity.kind.value if entity.kind else None,
        book_ids=entity.book_ids,
        chapter_ids=entity.chapter_ids,
        highlight_ids=entity.highlight_ids,
        tag_ids=entity.tag_ids,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def note_with_links_to_schema(view: NoteWithLinksView) -> NoteWithLinks:
    """Convert a note view DTO to its response schema."""
    return NoteWithLinks(
        id=view.id,
        user_id=view.user_id,
        title=view.title,
        body=view.body,
        kind=view.kind.value if view.kind else None,
        book_ids=list(view.book_ids),
        chapter_ids=list(view.chapter_ids),
        highlight_ids=list(view.highlight_ids),
        tag_ids=list(view.tag_ids),
        created_at=view.created_at,
        updated_at=view.updated_at,
        chapters=[NoteLinkedChapter(id=chapter.id, name=chapter.name) for chapter in view.chapters],
        highlights=[
            NoteLinkedHighlight(id=highlight.id, text=highlight.text[:HIGHLIGHT_SNIPPET_LENGTH])
            for highlight in view.highlights
        ],
        tags=[NoteLinkedTag(id=tag.id, name=tag.name) for tag in view.tags],
        flashcards=[
            Flashcard(
                id=fc.id,
                user_id=fc.user_id,
                book_id=fc.book_id,
                highlight_id=fc.highlight_id,
                chapter_id=fc.chapter_id,
                note_id=fc.note_id,
                question=fc.question,
                answer=fc.answer,
            )
            for fc in view.flashcards
        ],
    )


@router.post(
    "/notes",
    response_model=NoteCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_note(
    request: NoteCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: CreateNoteUseCase = Depends(inject_use_case(container.notes.create_note_use_case)),
) -> NoteCreateResponse:
    note_entity = await use_case.create_note(
        user_id=current_user.id.value,
        title=request.title,
        body=request.body,
        kind=request.kind,
        book_id=request.book_id,
        chapter_ids=request.chapter_ids,
        highlight_ids=request.highlight_ids,
        tag_ids=request.tag_ids,
    )
    return NoteCreateResponse(
        success=True,
        message="Note created successfully",
        note=note_entity_to_schema(note_entity),
    )


@router.get(
    "/notes/{note_id}",
    response_model=NoteWithLinks,
    status_code=status.HTTP_200_OK,
)
async def get_note(
    note_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: GetNoteUseCase = Depends(inject_use_case(container.notes.get_note_use_case)),
) -> NoteWithLinks:
    view = await use_case.get_note(note_id=note_id, user_id=current_user.id.value)
    return note_with_links_to_schema(view)


@router.get(
    "/books/{book_id}/notes",
    response_model=CollectionResponse[NoteWithLinks],
    status_code=status.HTTP_200_OK,
)
async def get_notes_for_book(
    book_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    kind: Annotated[NoteKindLiteral | None, Query()] = None,
    chapter_id: Annotated[int | None, Query()] = None,
    highlight_id: Annotated[int | None, Query()] = None,
    tag_id: Annotated[int | None, Query()] = None,
    use_case: GetNotesByBookUseCase = Depends(
        inject_use_case(container.notes.get_notes_by_book_use_case)
    ),
) -> CollectionResponse[NoteWithLinks]:
    views = await use_case.get_notes(
        book_id=book_id,
        user_id=current_user.id.value,
        kind=kind,
        chapter_id=chapter_id,
        highlight_id=highlight_id,
        tag_id=tag_id,
    )
    return CollectionResponse[NoteWithLinks](
        items=[note_with_links_to_schema(view) for view in views]
    )


@router.put(
    "/notes/{note_id}",
    response_model=NoteUpdateResponse,
    status_code=status.HTTP_200_OK,
)
async def update_note(
    note_id: int,
    request: NoteUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: UpdateNoteUseCase = Depends(inject_use_case(container.notes.update_note_use_case)),
) -> NoteUpdateResponse:
    note_entity = await use_case.update_note(
        note_id=note_id,
        user_id=current_user.id.value,
        title=request.title,
        body=request.body,
        kind=request.kind,
        chapter_ids=request.chapter_ids,
        highlight_ids=request.highlight_ids,
        tag_ids=request.tag_ids,
    )
    return NoteUpdateResponse(
        success=True,
        message="Note updated successfully",
        note=note_entity_to_schema(note_entity),
    )


@router.delete(
    "/notes/{note_id}",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
)
async def delete_note(
    note_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: DeleteNoteUseCase = Depends(inject_use_case(container.notes.delete_note_use_case)),
) -> SuccessResponse:
    await use_case.delete_note(note_id=note_id, user_id=current_user.id.value)
    return SuccessResponse(success=True, message="Note deleted successfully")
