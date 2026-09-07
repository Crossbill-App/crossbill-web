"""Read model for one file of a publication, served to the web reader.

The manifest (M1.1) names every file the reader will ask for; this is the view
that answers one of those asks. It is a dead end like any read model -- rendered
into an HTTP response and never fed back into a command. See
``docs/adr/0001-read-models-and-query-services.md``.
"""

from dataclasses import dataclass
from typing import Protocol

from src.domain.common.value_objects.ids import BookId, UserId


@dataclass(frozen=True)
class PublicationResourceView:
    """One file of a publication, exactly as the EPUB stores it.

    Attributes:
        media_type: The media type the package document declares for this file,
            and therefore the one the manifest lists for it. The bytes are
            served under it unchanged.
        content: The file's decompressed bytes, byte-for-byte what the EPUB
            holds.
        version: An opaque token identifying these exact bytes *within this
            book*. It changes when the book's stored EPUB is replaced or when
            the file's contents change, which is what makes it usable as an
            HTTP entity tag. Not a hash of the content itself: it is derived
            from the archive's own checksum, which is read from the central
            directory rather than computed.
    """

    media_type: str
    content: bytes
    version: str


class PublicationResourceQueryProtocol(Protocol):
    """Port for reading one file out of a book's stored EPUB."""

    async def get_publication_resource(
        self, book_id: BookId, user_id: UserId, path: str
    ) -> PublicationResourceView | None:
        """Return one file of a user's publication, or ``None`` when they have no such book.

        Args:
            book_id: The book whose EPUB holds the file.
            user_id: The user the book must belong to.
            path: The file's path inside the EPUB container, relative to the
                container root and **decoded** -- the manifest's percent-encoded
                href with its encoding undone exactly once, which is the archive
                member's own name.

        Raises:
            EbookFileNotFoundError: If the book exists but no EPUB is stored for
                it -- distinct from ``None``, which means the book does not.
            InvalidEbookError: If the stored EPUB cannot be parsed.
            PublicationResourceNotFoundError: If the publication lists no such
                file.
        """
        ...
