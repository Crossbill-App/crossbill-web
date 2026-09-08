"""Our own shape for the publication session endpoint, as against Readium's shapes."""

from pydantic import BaseModel


class PublicationSession(BaseModel):
    """What a reader learns when it is handed a publication cookie.

    The cookie itself is httpOnly, so the page that asked for it cannot read
    when it dies. This is the one thing it needs back -- named ``expires_in``,
    in seconds, like the token response it schedules alongside.
    """

    expires_in: int
