"""Our own shape for the publication session endpoint, as against Readium's shapes."""

from pydantic import BaseModel


class PublicationSession(BaseModel):
    """What a reader learns when it is handed a publication cookie."""

    expires_in: int
