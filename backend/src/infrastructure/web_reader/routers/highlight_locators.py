"""Where a book's highlights are in the EPUB, for the reader to draw and jump to.

Two routes over one derivation (M3.1, #745; M3.2, #746), and they sit on
opposite sides of the publication cookie on purpose.

``GET /highlights/{id}/locator`` places **one** highlight so the reader can jump
to it. It is Bearer-authenticated and outside the ``/readium`` prefix. The
cookie exists for one reason (ADR-0004, *Amendment 1*): a navigator's iframe
loads a resource as a plain browser request and cannot carry the SPA's access
token. Nothing about that route is loaded that way -- the app fetches it with
``fetch`` exactly as it fetches every other highlight view -- and scoping it
under the cookie's path would widen that credential from *read this
publication* to *read any of this user's highlights*, since the route is keyed
by highlight rather than by book.

``GET /readium/books/{id}/highlight-locators`` places **every** highlight of one
book, which is what a reader drawing decorations asks for. It takes either
credential, and being under the cookie's path is the point rather than a cost:
the cookie is minted per book and this route answers for that one book, so what
it opens is exactly *read this publication* -- the scope the cookie already had.
It has to be reachable that way, because unlike the jump above this is fetched
**while reading**, from a page whose access token may have lapsed behind a tab
that was left open, and a decoration layer that quietly stopped redrawing would
be a worse failure than one that never drew at all.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.application.web_reader.queries.get_highlight_locators_use_case import (
    GetHighlightLocatorsUseCase,
)
from src.application.web_reader.queries.highlight_locators import DerivedHighlightLocator
from src.core import container
from src.domain.common.value_objects.ids import BookId, HighlightId
from src.domain.identity.entities.user import User
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.common.schemas.response_wrappers import CollectionResponse
from src.infrastructure.identity.dependencies import get_current_user
from src.infrastructure.web_reader.dependencies import PublicationReader
from src.infrastructure.web_reader.schemas.highlight_locator_schemas import (
    HighlightLocatorResponse,
    build_highlight_locator,
)

router = APIRouter(prefix="", tags=["highlights"])

# The book-scoped read is the reader's own, so it lives under the reader's
# prefix -- which is also the publication cookie's path scope.
book_router = APIRouter(prefix="/readium", tags=["readium"])


def _locator_response(derived: DerivedHighlightLocator) -> HighlightLocatorResponse:
    """Render one derived locator in the coordinates a navigator speaks."""
    answer = build_highlight_locator(derived)
    return HighlightLocatorResponse(
        highlight_id=derived.highlight_id,
        locator=answer.locator,
        unavailable=answer.unavailable,
    )


@router.get(
    "/highlights/{highlight_id}/locator",
    response_model=HighlightLocatorResponse,
    status_code=status.HTTP_200_OK,
)
async def get_highlight_locator(
    highlight_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    use_case: GetHighlightLocatorsUseCase = Depends(
        inject_use_case(container.web_reader.get_highlight_locators_use_case)
    ),
) -> HighlightLocatorResponse:
    """
    Get the Readium locator for one highlight, for jumping to it in the web reader.

    The locator is derived from the highlight's stored KOReader position against
    the book's EPUB at request time and is never stored, so it is verified
    against the highlight's own text before being returned. A highlight that
    cannot be placed answers 200 with a null locator and a reason -- the
    highlight itself is intact, and only this view of it is missing.

    A highlight that does not exist, or belongs to another user, answers 404.
    """
    return _locator_response(
        await use_case.for_highlight(HighlightId(highlight_id), current_user.id)
    )


@book_router.get(
    "/books/{book_id}/highlight-locators",
    response_model=CollectionResponse[HighlightLocatorResponse],
    status_code=status.HTTP_200_OK,
)
async def get_book_highlight_locators(
    book_id: int,
    current_user: PublicationReader,
    use_case: GetHighlightLocatorsUseCase = Depends(
        inject_use_case(container.web_reader.get_highlight_locators_use_case)
    ),
) -> CollectionResponse[HighlightLocatorResponse]:
    """
    Get where every one of a book's highlights is in its EPUB, for drawing them.

    The whole live list, in highlight-id order, one entry per highlight and
    never a silent omission: each carries either a verified locator or a reason
    it has none, so a reader can tell a highlight it must not draw from one it
    was never told about. Highlights the reader has deleted are simply absent.

    This is the one caller that legitimately asks for a book's entire list. Every
    other view narrows to the highlights it will render, because conversion costs
    per highlight (ADR-0004 §4, and the measurement in *Amendment 5*) -- but a
    reader drawing every decoration in a book is asking for all of them by
    construction, and on a heavily annotated, flatly structured book that is a
    second or more. The browser must therefore treat this as arriving *after*
    the text rather than as something to open the book behind.

    Authenticated by either the SPA's Bearer token or the book's publication
    cookie, unlike the single-highlight route above: this one is fetched while
    the book is open, and it answers for the one book the cookie already names.

    A book that does not exist, or belongs to another user, answers 404.
    """
    derived = await use_case.for_book(BookId(book_id), current_user.id)
    return CollectionResponse(items=[_locator_response(placed) for placed in derived.values()])
