"""Where a book's highlights sit in its EPUB, for the reader to draw and jump to.

Outside the ``/readium`` prefix because that prefix is the publication cookie's
path scope, and widening that credential to a user's highlights buys nothing:
the app fetches these with a Bearer that refreshes on 401.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from starlette import status

from src.application.web_reader.queries.get_book_highlight_locators_use_case import (
    GetBookHighlightLocatorsUseCase,
)
from src.application.web_reader.queries.highlight_locators import HighlightLocatorView
from src.core import container
from src.domain.common.value_objects.ids import BookId
from src.domain.identity import User
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.common.schemas.response_wrappers import CollectionResponse
from src.infrastructure.identity.dependencies import get_current_user
from src.infrastructure.web_reader.schemas.locator_builders import served_locator_schema
from src.infrastructure.web_reader.schemas.locator_schemas import HighlightLocatorResponse

router = APIRouter(tags=["highlights"])


@router.get(
    "/books/{book_id}/highlight-locators",
    response_model=CollectionResponse[HighlightLocatorResponse],
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
)
async def get_book_highlight_locators(
    book_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: GetBookHighlightLocatorsUseCase = Depends(
        inject_use_case(container.web_reader.get_book_highlight_locators_use_case)
    ),
) -> CollectionResponse[HighlightLocatorResponse]:
    """
    Get where every one of a book's live highlights is in its EPUB.

    One entry per highlight, in id order, each carrying either a locator or a
    reason there is none -- so a reader can tell a highlight it must not draw
    from one it was never told about. Deleted highlights are simply absent.

    A locator here was derived when the highlight or the book's EPUB was last
    synced, and is withheld once the book's EPUB no longer matches the file it
    came from. Nothing is derived to answer this request.

    A book that does not exist, or belongs to another user, answers 404.
    """
    views = await use_case.get_book_highlight_locators(BookId(book_id), current_user.id)
    return CollectionResponse(items=[_locator_response(view) for view in views])


def _locator_response(view: HighlightLocatorView) -> HighlightLocatorResponse:
    return HighlightLocatorResponse(
        highlight_id=view.highlight_id,
        locator=served_locator_schema(view.locator) if view.locator else None,
        unavailable=view.unavailable,
    )
