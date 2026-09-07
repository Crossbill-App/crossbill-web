"""FastAPI dependencies shared by the web reader's routes."""

from typing import Annotated

from fastapi import Cookie, Depends

from src.domain.common.exceptions import AuthenticationError
from src.domain.identity.entities.user import User
from src.infrastructure.identity.dependencies import (
    CREDENTIALS_ERROR,
    UserByIdUseCase,
    get_current_user_optional,
    load_authenticated_user,
)
from src.infrastructure.web_reader.services.publication_token_service import (
    PUBLICATION_COOKIE_NAME,
    verify_publication_token,
)


async def get_publication_reader(
    book_id: int,
    bearer_user: Annotated[User | None, Depends(get_current_user_optional)],
    use_case: UserByIdUseCase,
    publication_access: Annotated[str | None, Cookie(alias=PUBLICATION_COOKIE_NAME)] = None,
) -> User:
    """Authenticate whoever is reading a publication, by either credential they may hold.

    The rule and its reasons are ADR-0004, *Amendment 1* (#737).

    The SPA holds a Bearer token and sends it; a navigator's iframe holds
    nothing and sends the publication cookie the SPA asked for (POST
    ``/readium/books/{book_id}/session``). Both are accepted here, so every web
    reader route -- manifest, resources, position list -- gains the second one
    together rather than one at a time, which is what makes "who may read this"
    a single rule with one place to get wrong.

    That the manifest accepts the cookie too widens nothing: a cookie is only
    ever issued to a caller that proved possession of a Bearer token for this
    same book, so it opens no door its holder could not already open.

    The Bearer token wins when both are present, and a Bearer token that is
    present and broken fails the request rather than falling through to the
    cookie -- ``get_current_user_optional`` is what draws that line.

    Raises:
        AuthenticationError: If neither credential is presented, or the cookie
            does not verify, or it verifies for a different book than the one
            being read. The last is 401 rather than 404 because the caller has
            not been authenticated *for this book* at all: answering 404 would
            mean telling a credential scoped to book A whether book B exists.
    """
    if bearer_user is not None:
        return bearer_user
    if publication_access is None:
        raise AuthenticationError(CREDENTIALS_ERROR)
    claims = verify_publication_token(publication_access)
    if claims is None or claims.book_id != book_id:
        raise AuthenticationError(CREDENTIALS_ERROR)
    return await load_authenticated_user(use_case, claims.user_id)


PublicationReader = Annotated[User, Depends(get_publication_reader)]
