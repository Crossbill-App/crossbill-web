"""Read model for one file of a publication, served to the web reader.

The manifest (M1.1) names every file the reader will ask for; this is the view
that answers one of those asks. It is a dead end like any read model -- rendered
into an HTTP response and never fed back into a command. See
``docs/adr/0001-read-models-and-query-services.md``.
"""

from dataclasses import dataclass
from typing import Protocol

from src.domain.common.value_objects.ids import BookId, UserId

# A caller that holds whatever version there is, however new. Its only source is
# an ``If-None-Match: *``, but the read model has no reason to know that: it
# says "give me this only if I do not already have it", which is a question
# about versions rather than about HTTP.
ANY_VERSION = "*"


@dataclass(frozen=True)
class PublicationResourceView:
    """One file of a publication, exactly as the EPUB stores it.

    Attributes:
        media_type: The media type the package document declares for this file,
            and therefore the one the manifest lists for it. The bytes are
            served under it unchanged.
        content: The file's decompressed bytes, byte-for-byte what the EPUB
            holds -- or ``None`` when the caller said it already holds this
            version, in which case the file was never read. Reading a member is
            the expensive half of this view, so not reading it is the point of
            asking rather than an optimisation on the side.
        version: An opaque token identifying these exact bytes. It changes
            whenever the book's stored EPUB changes, so it is safe to use as an
            HTTP entity tag.
    """

    media_type: str
    content: bytes | None
    version: str


class PublicationResourceQueryProtocol(Protocol):
    """Port for reading one file out of a book's stored EPUB."""

    async def get_publication_resource(
        self, book_id: BookId, user_id: UserId, path: str, known_versions: frozenset[str]
    ) -> PublicationResourceView | None:
        """Return one file of a user's publication, or ``None`` when they have no such book.

        Args:
            book_id: The book whose EPUB holds the file.
            user_id: The user the book must belong to.
            path: The file's path inside the EPUB container, relative to the
                container root and **decoded** -- the manifest's percent-encoded
                href with its encoding undone exactly once, which is the archive
                member's own name.
            known_versions: Versions the caller says it already holds, or
                ``{ANY_VERSION}``. When the file's version is among them the
                view comes back with no content and the member is never read.

        Raises:
            EbookFileNotFoundError: If the book exists but no EPUB is stored for
                it -- distinct from ``None``, which means the book does not.
            InvalidEbookError: If the stored EPUB cannot be parsed, or the file
                is too large to serve.
            PublicationResourceNotFoundError: If the publication lists no such
                file.
        """
        ...
