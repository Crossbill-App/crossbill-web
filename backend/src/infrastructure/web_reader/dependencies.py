"""FastAPI dependencies shared by the web reader's routes."""

from typing import Annotated

from fastapi import Depends

from src.domain.identity.entities.user import User
from src.infrastructure.identity import get_current_user


async def get_publication_reader(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Authenticate whoever is reading a publication.

    A Bearer token is the only credential today, and this adds nothing to it. It
    exists as a seam rather than as a rule: M1.4 (#737) has to let a navigator's
    iframe load resource URLs, which cannot carry an in-memory Bearer token, and
    the candidate is a short-lived httpOnly publication cookie (ADR-0004,
    *Pending*). Accepting a second credential is then an edit here, and every
    web reader route -- manifest, resources, and the position list to come --
    gains it together instead of one at a time.
    """
    return user


PublicationReader = Annotated[User, Depends(get_publication_reader)]
