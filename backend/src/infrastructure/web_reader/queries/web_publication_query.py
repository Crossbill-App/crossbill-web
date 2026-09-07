"""Query adapter for the Web Publication Manifest view.

The one row Postgres holds for this view is the book itself -- which answers
whether the caller may see it, and which EPUB to open, and which
:func:`~src.infrastructure.web_reader.queries.stored_epub.load_stored_epub`
reads. Everything the manifest renders comes out of that EPUB, so the adapter is
constructed with the file store and the parser as well as the session, the way
``ReadingSessionQuery`` takes the file store to read a session's text back out
of a book.

Nothing here decides anything: the EPUB's own package document is the authority
on the reading order, and the only substitution the adapter makes is the stored
title, and only when the package document states none.
"""

import asyncio
from dataclasses import replace

from sqlalchemy.ext.asyncio import AsyncSession

from src.application.library.protocols.file_repository import FileRepositoryProtocol
from src.application.web_reader.protocols.publication_parser import PublicationParserProtocol
from src.application.web_reader.publications import ParsedPublication
from src.domain.common.value_objects.ids import BookId, UserId
from src.infrastructure.web_reader.queries.stored_epub import load_stored_epub


class WebPublicationQuery:
    """Serves a book's publication structure from its stored EPUB."""

    def __init__(
        self,
        db: AsyncSession,
        file_repository: FileRepositoryProtocol,
        publication_parser: PublicationParserProtocol,
    ) -> None:
        self.db = db
        self.file_repository = file_repository
        self.publication_parser = publication_parser

    async def get_web_publication(
        self, book_id: BookId, user_id: UserId
    ) -> ParsedPublication | None:
        """Return the publication for a user's book, or ``None`` when they have no such book.

        Raises:
            EbookFileNotFoundError: If the book exists but no EPUB is stored for it.
            InvalidEbookError: If the stored EPUB cannot be parsed.
        """
        stored = await load_stored_epub(self.db, self.file_repository, book_id, user_id)
        if stored is None:
            return None

        # Parsing an EPUB is CPU-bound and proportional to the book, so it runs
        # off the event loop: this is a plain GET a reader issues on every open,
        # and a large publication parsed inline would stall every other request
        # in the process for the duration.
        publication = await asyncio.to_thread(
            self.publication_parser.parse_publication, stored.content
        )
        if publication.metadata.title:
            return publication
        # An EPUB with no dc:title is invalid but does occur, and a manifest
        # without one is unrenderable, so the library's title stands in.
        return replace(publication, metadata=replace(publication.metadata, title=stored.title))
