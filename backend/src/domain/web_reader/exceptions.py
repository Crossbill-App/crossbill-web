"""Web reader domain exceptions."""

from src.domain.common.exceptions import EntityNotFoundError


class PublicationResourceNotFoundError(EntityNotFoundError):
    """Raised when a publication does not contain the requested file.

    Distinct from ``BookNotFoundError`` and ``EbookFileNotFoundError``: the book
    is there, its EPUB is readable, and the path simply names nothing the
    publication offers -- a stale href, a typo, or somebody probing for the
    package document. All three answer 404, and keeping them apart is what lets
    the logs tell a broken reader from a missing file.
    """

    def __init__(self, path: str) -> None:
        super().__init__("Publication resource", path)
        self.path = path
