"""Read model for one file of a publication, served out of the book's EPUB."""

from dataclasses import dataclass
from typing import Protocol

from src.domain.common.value_objects.ids import BookId, UserId


@dataclass(frozen=True)
class PublicationResourceView:
    """One file of a publication, byte-for-byte as the archive holds it.

    Attributes:
        media_type: The media type the stored index declares for the file.
        content: The member's decompressed bytes, or ``None`` when the caller
            already holds this version -- in which case the member was never
            read, which is the point of asking rather than an optimisation.
        version: An opaque token for the stored EPUB these bytes came from.
    """

    media_type: str
    content: bytes | None
    version: str


class PublicationResourceQueryProtocol(Protocol):
    async def get_publication_resource(
        self, book_id: BookId, user_id: UserId, path: str, known_versions: frozenset[str] | None
    ) -> PublicationResourceView | None:
        """Return one file of a user's publication, or ``None`` when no index is stored.

        ``path`` is the file's path inside the EPUB container, decoded exactly
        once -- a manifest href with its percent-encoding undone, which is the
        archive member's own name. ``known_versions`` holds the versions the
        caller already has; ``None`` is a caller that holds whatever version
        there is, and is not a version itself so that no version can spell it.

        An absent index is not an absent book: ``None`` covers both a book the
        user does not own and one whose index has yet to be derived, and the
        caller is what separates them.

        Raises:
            EbookFileNotFoundError: If the index is stored but its EPUB is not.
            InvalidEbookError: If the archive or the member cannot be read.
            PublicationResourceNotFoundError: If the index lists no such file,
                or the archive holds no such member.

        Neither the missing EPUB nor the missing member is reached once a
        version matched, which is answered before the file store is read.
        """
        ...
