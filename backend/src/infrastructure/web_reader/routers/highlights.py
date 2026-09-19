"""Making a highlight in the browser (M4.2, #751).

Outside the ``/readium`` prefix, like the highlight-locator reads it answers for:
that prefix is the publication cookie's path scope, and a credential a book's own
markup can make the browser spend must never reach a write (ADR-0004, *Amendment
1*). This is Bearer-only, and not version-gated -- no plugin calls it.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from starlette import status

from src.application.web_reader.commands.create_highlight_from_locator_use_case import (
    CreateHighlightFromLocatorUseCase,
)
from src.core import container
from src.domain.identity import User
from src.domain.reading.entities.highlight import Highlight
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.identity.dependencies import get_current_user
from src.infrastructure.web_reader.schemas.highlight_schemas import (
    CreatedHighlightResponse,
    SelectionHighlightCreate,
)
from src.infrastructure.web_reader.schemas.locator_builders import anchor_locator

router = APIRouter(tags=["highlights"])


@router.post(
    "/books/{book_id}/highlights",
    response_model=CreatedHighlightResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_200_OK: {
            "model": CreatedHighlightResponse,
            "description": "The book already held this passage; the stored highlight is returned.",
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "The selected text is not in this book, or is in too many places."
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "The book's stored file cannot be read, so nothing can be placed in it."
        },
    },
)
async def create_highlight(
    book_id: int,
    body: SelectionHighlightCreate,
    response: Response,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: CreateHighlightFromLocatorUseCase = Depends(
        inject_use_case(container.web_reader.create_highlight_from_locator_use_case)
    ),
) -> CreatedHighlightResponse:
    """Store a passage the reader selected in the browser.

    The selection is converted to the canonical KOReader xpointers before anything
    is stored (ADR-0004 §2) and refused with 422 if the book does not hold the
    selected text, or holds it in so many places that which one was meant cannot be
    said. What is stored is an ordinary highlight, so it reaches the e-reader
    through the sync that already exists and shows up in every view that renders
    one.

    The same passage marked twice is one highlight: a selection whose text the book
    already holds answers **200** with the stored highlight instead of 201, and one
    the reader had deleted comes back rather than being stored again. That stored
    highlight may sit at another occurrence of the same words, so a reader that
    needs to draw it should ask ``GET /highlights/{id}/locator`` where it is rather
    than assume it is where this selection was.

    A selection may name a ``device_color`` in place of a label, and is then filed
    under the book's style for that colour and drawer -- created if the book has
    none yet -- the way the e-reader's own highlights are.
    """
    result = await use_case.create_highlight(
        book_id=book_id,
        user_id=current_user.id.value,
        locator=anchor_locator(body.locator),
        device_datetime=body.datetime.replace(tzinfo=None),
        note=body.note,
        highlight_style_id=body.highlight_style_id,
        device_color=body.device_color,
        device_style=body.device_style,
    )
    if not result.created:
        response.status_code = status.HTTP_200_OK
    return _created_highlight(result.highlight)


def _created_highlight(highlight: Highlight) -> CreatedHighlightResponse:
    """Render the stored highlight as the browser gets it back."""
    return CreatedHighlightResponse(
        id=highlight.id.value,
        book_id=highlight.book_id.value,
        chapter_id=highlight.chapter_id.value if highlight.chapter_id else None,
        text=highlight.text,
        note=highlight.koreader_note,
        highlight_style_id=highlight.highlight_style_id.value
        if highlight.highlight_style_id
        else None,
        start_xpoint=highlight.xpoints.start.to_string() if highlight.xpoints else None,
        end_xpoint=highlight.xpoints.end.to_string() if highlight.xpoints else None,
        datetime=highlight.datetime,
    )
