"""Query adapter for the Web Publication Manifest view.

The one row Postgres holds for this view is the book itself -- which answers
whether the caller may see it, and which EPUB to open, and which
:class:`~src.infrastructure.web_reader.queries.stored_epub.PublicationQuery`
reads. Everything the manifest renders comes out of that EPUB, so the adapter is
constructed with the file store and the parser as well as the session, the way
``ReadingSessionQuery`` takes the file store to read a session's text back out
of a book.

Nothing here decides anything: the EPUB's own package document is the authority
on the reading order, and the only substitution the adapter makes is the stored
title, and only when the package document states none.
"""

from dataclasses import replace

from src.application.web_reader.publications import ParsedPublication
from src.domain.common.value_objects.ids import BookId, UserId
from src.infrastructure.web_reader.queries.stored_epub import PublicationQuery, StoredEpub


class WebPublicationQuery(PublicationQuery):
    """Serves a book's publication structure from its stored EPUB."""

    async def get_web_publication(
        self, book_id: BookId, user_id: UserId
    ) -> ParsedPublication | None:
        """Return the publication for a user's book, or ``None`` when they have no such book.

        Raises:
            EbookFileNotFoundError: If the book exists but no EPUB is stored for it.
            InvalidEbookError: If the stored EPUB cannot be parsed.
        """
        return await self._read_publication(book_id, user_id, self._titled_publication)

    def _titled_publication(self, stored: StoredEpub) -> ParsedPublication:
        """Parse the publication, giving it the library's title if it states none."""
        publication = self.publication_parser.parse_publication(stored.content)
        if publication.metadata.title:
            return publication
        # An EPUB with no dc:title is invalid but does occur, and a manifest
        # without one is unrenderable, so the library's title stands in.
        return replace(publication, metadata=replace(publication.metadata, title=stored.title))
