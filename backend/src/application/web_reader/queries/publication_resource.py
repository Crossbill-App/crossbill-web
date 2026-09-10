"""Read model for one file of a publication, served out of the book's EPUB."""

from dataclasses import dataclass
from typing import Protocol

from src.domain.common.value_objects.ids import BookId, UserId


@dataclass(frozen=True)
class PublicationResourceView:
    """One file of a publication, byte-for-byte as the archive holds it.

    Attributes:
        media_type: The media type the stored index declares for the file.
        content: The member's decompressed bytes.
    """

    media_type: str
    content: bytes


class PublicationResourceQueryProtocol(Protocol):
    async def get_publication_resource(
        self, book_id: BookId, user_id: UserId, path: str
    ) -> PublicationResourceView | None:
        """Return one file of a user's publication, or ``None`` when no index is stored.

        ``path`` is the file's path inside the EPUB container, decoded exactly
        once -- a manifest href with its percent-encoding undone, which is the
        archive member's own name.

        An absent index is not an absent book: ``None`` covers both a book the
        user does not own and one whose index has yet to be derived, and the
        caller is what separates them.

        Raises:
            EbookFileNotFoundError: If the index is stored but its EPUB is not.
            InvalidEbookError: If the archive or the member cannot be read.
            PublicationResourceNotFoundError: If the index lists no such file,
                or the archive holds no such member.
        """
        ...
