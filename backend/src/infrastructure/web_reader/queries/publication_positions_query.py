"""Query adapter computing a book's Readium position list from its stored EPUB.

A position is a synthetic page: an EPUB's reflowable documents have no pages of
their own, so Readium cuts each one into :data:`POSITION_LENGTH`-byte pieces and
calls each piece a position. That is a convention rather than a derivation --
what matters is only that every reader of one publication agrees on the same
numbering -- so this follows the Readium toolkits' recipe exactly, rather than
inventing a better one that no other implementation would reproduce.

The lengths come from the archive's central directory, never from decompressing
anything: the number wanted is each member's uncompressed size, which the
directory already states, so a book's position list costs no inflation at all
(see #773, which is about not decompressing on trust).

The publication is parsed per request, as the manifest and resource endpoints
parse it, because the parse is what says which documents the reading order holds
and how each is laid out. Holding the parse -- and this list computed beside it
-- in a per-book cache is deferred to the measurement in #745 (ADR-0004 §4);
until then no endpoint grows a private shortcut ahead of that.
"""

import asyncio
import math
import zipfile
from collections.abc import Mapping, Sequence
from io import BytesIO
from urllib.parse import unquote

from sqlalchemy.ext.asyncio import AsyncSession

from src.application.library.protocols.file_repository import FileRepositoryProtocol
from src.application.web_reader.protocols.publication_parser import PublicationParserProtocol
from src.application.web_reader.publications import PublicationLayout, PublicationResource
from src.application.web_reader.queries.publication_positions import PublicationPosition
from src.domain.common.value_objects.ids import BookId, UserId
from src.infrastructure.web_reader.queries.stored_epub import StoredEpub, load_stored_epub

# Bytes of a reflowable document per position, which is the length every Readium
# toolkit uses. The number is arbitrary and the agreement is not: a locator
# saying "position 42" means nothing unless the reader that reads it cut the
# book the same way the writer did.
POSITION_LENGTH = 1024


class PublicationPositionsQuery:
    """Serves a book's position list, computed from its stored EPUB."""

    def __init__(
        self,
        db: AsyncSession,
        file_repository: FileRepositoryProtocol,
        publication_parser: PublicationParserProtocol,
    ) -> None:
        self.db = db
        self.file_repository = file_repository
        self.publication_parser = publication_parser

    async def get_publication_positions(
        self, book_id: BookId, user_id: UserId
    ) -> tuple[PublicationPosition, ...] | None:
        """Return the positions of a user's publication, or ``None`` for no such book.

        Raises:
            EbookFileNotFoundError: If the book exists but no EPUB is stored for it.
            InvalidEbookError: If the stored EPUB cannot be parsed.
        """
        stored = await load_stored_epub(self.db, self.file_repository, book_id, user_id)
        if stored is None:
            return None
        # Parsing the publication and reading the central directory are both
        # blocking and both CPU-bound, so they share one hop off the event loop
        # rather than stalling every other request for the duration.
        return await asyncio.to_thread(self._compute_positions, stored)

    def _compute_positions(self, stored: StoredEpub) -> tuple[PublicationPosition, ...]:
        """Parse the publication and cut its reading order into positions."""
        publication = self.publication_parser.parse_publication(stored.content)
        with zipfile.ZipFile(BytesIO(stored.content)) as archive:
            # `file_size` is the member's uncompressed length as the central
            # directory declares it, so the whole list is read without touching
            # a compressed stream.
            sizes = {entry.filename: entry.file_size for entry in archive.infolist()}
        return position_list(publication.reading_order, sizes)


def position_list(
    reading_order: Sequence[PublicationResource],
    sizes: Mapping[str, int],
) -> tuple[PublicationPosition, ...]:
    """Cut a reading order into positions, the way the Readium toolkits cut one.

    Every position is numbered across the whole publication rather than within
    its resource, so ``position`` is what a reader displays and
    ``total_progression`` is where the progress bar sits.

    Args:
        reading_order: The publication's reading order, in order. Only these
            produce positions; a stylesheet or an image is not somewhere a
            reader can be.
        sizes: Each archive member's uncompressed length, keyed by the member's
            own name -- which is a reading-order href decoded exactly once. A
            resource the map does not name is counted as empty, and so still
            gets the one position every resource is worth.
    """
    counts = [
        _position_count(resource, sizes.get(unquote(resource.href), 0))
        for resource in reading_order
    ]
    total = sum(counts)

    positions: list[PublicationPosition] = []
    for resource, count in zip(reading_order, counts, strict=True):
        for index in range(count):
            positions.append(
                PublicationPosition(
                    href=resource.href,
                    media_type=resource.media_type,
                    position=len(positions) + 1,
                    progression=index / count,
                    total_progression=len(positions) / total,
                )
            )
    return tuple(positions)


def _position_count(resource: PublicationResource, size: int) -> int:
    """How many positions one reading-order resource is worth.

    A fixed-layout resource is one page by construction -- it is a spread the
    author typeset, and cutting it up would number places that are all visible
    at once -- so it gets exactly one position however large its file is.

    A reflowable one gets a position per :data:`POSITION_LENGTH` bytes of
    markup, and never fewer than one: an empty or near-empty chapter is still a
    place a reader can be, and a resource worth zero positions would be
    unreachable in a list that is addressed by position.
    """
    if resource.layout is PublicationLayout.FIXED:
        return 1
    return max(1, math.ceil(size / POSITION_LENGTH))
