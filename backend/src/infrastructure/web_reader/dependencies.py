"""FastAPI dependencies for the routes a navigator's iframe loads.

An iframe load carries no ``Authorization`` header, so these routes authenticate
on the publication cookie alone (#800, #801).
"""

from typing import Annotated

from fastapi import Cookie, Depends

from src.domain.common.exceptions import AuthenticationError
from src.domain.identity.entities.user import User
from src.infrastructure.identity import UserByIdUseCase, load_authenticated_user
from src.infrastructure.web_reader.services.publication_token_service import (
    PUBLICATION_COOKIE_NAME,
    verify_publication_token,
)

# Distinct from identity's wording so a log line says which credential was
# missing. The client is answered the same generic message either way.
NO_PUBLICATION_COOKIE = "No valid publication cookie"


async def get_publication_reader(
    book_id: int,
    use_case: UserByIdUseCase,
    publication_access: Annotated[str | None, Cookie(alias=PUBLICATION_COOKIE_NAME)] = None,
) -> User:
    """Authenticate the reader of one book's publication by its cookie alone.

    Raises:
        AuthenticationError: If no valid cookie for this book is presented.
    """
    if publication_access is None:
        raise AuthenticationError(NO_PUBLICATION_COOKIE)
    claims = verify_publication_token(publication_access)
    # A cookie naming another book is 401 and not 404: the caller has not been
    # authenticated here at all, and 404 would tell book A's holder of book B.
    if claims is None or claims.book_id != book_id:
        raise AuthenticationError(NO_PUBLICATION_COOKIE)
    return await load_authenticated_user(use_case, claims.user_id)


PublicationReader = Annotated[User, Depends(get_publication_reader)]
