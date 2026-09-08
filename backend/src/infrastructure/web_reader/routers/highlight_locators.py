"""Where one highlight is in the EPUB, for the reader to jump to it (M3.1, #745).

Outside the ``/readium`` prefix, and Bearer-authenticated rather than taking the
publication cookie. The cookie exists for one reason (ADR-0004, *Amendment 1*):
a navigator's iframe loads a resource as a plain browser request and cannot
carry the SPA's access token. Nothing about this route is loaded that way -- the
app fetches it with ``fetch`` before or alongside opening the reader, exactly as
it fetches every other highlight view -- so it needs no second credential, and
scoping it under the cookie's path would widen that credential from *read this
publication* to *read this user's highlights*.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.application.web_reader.queries.get_highlight_locators_use_case import (
    GetHighlightLocatorsUseCase,
)
from src.core import container
from src.domain.common.value_objects.ids import HighlightId
from src.domain.identity.entities.user import User
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.identity.dependencies import get_current_user
from src.infrastructure.web_reader.schemas.highlight_locator_schemas import (
    HighlightLocatorResponse,
    build_highlight_locator,
)

router = APIRouter(prefix="", tags=["highlights"])


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
    derived = await use_case.for_highlight(HighlightId(highlight_id), current_user.id)
    answer = build_highlight_locator(derived)
    return HighlightLocatorResponse(
        highlight_id=derived.highlight_id,
        locator=answer.locator,
        unavailable=answer.unavailable,
    )
