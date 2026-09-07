"""Query adapter computing a book's Readium position list from its stored EPUB.

A position is a synthetic page: an EPUB's reflowable documents have no pages of
their own, so Readium cuts each one into :data:`POSITION_LENGTH`-byte pieces and
calls each piece a position. That is a convention rather than a derivation --
what matters is only that a publication is cut the same way every time it is
read -- so the arithmetic follows the Readium toolkits' recipe (go-toolkit
``pkg/parser/epub/positions_service.go``, kotlin-toolkit
``EpubPositionsService``) rather than a better one of our own invention:

- a reflowable resource is worth ``max(1, ceil(length / 1024))`` positions;
- ``progression`` is ``i / count`` for the ``i``-th position of its own
  resource, zero-based, so every resource opens at ``0.0``;
- ``totalProgression`` is ``(position - 1) / total``, so the book opens at
  ``0.0`` and its last position sits below ``1.0`` rather than at it;
- ``position`` is 1-based and runs on across resources;
- a fixed-layout resource is worth exactly one position.

**Two deliberate divergences from go-toolkit**, both narrowing what a number can
depend on:

*Length is the member's uncompressed size, not its compressed one.* The Go
toolkit measures the stored (deflated) length, which it documents as the
historical Adobe RMSDK-compatible strategy. Compressed length is a property of
whoever built the zip rather than of the book: recompressing an EPUB, or storing
one member and deflating the next, silently renumbers positions that highlights
and reading progress are expressed against. The uncompressed size is stated in
the same central directory at the same cost and does not move.

*Layout is read per reading-order item, not per publication.* Go decides once
for the whole book from the package metadata; our parser already resolves
``rendition:layout`` per spine item, and the manifest publishes it that way
(M1.1), so a mixed-layout publication would otherwise be numbered against a
layout the manifest denies.

Either way the lengths come from the archive's central directory and nothing is
decompressed to count them (see #773, which is about not decompressing on
trust).

The publication is parsed per request, as the manifest and resource endpoints
parse it, because the parse is what says which documents the reading order holds
and how each is laid out. Holding the parse -- and this list computed beside it
-- in a per-book cache is deferred to the measurement in #745 (ADR-0004 §4);
until then no endpoint grows a private shortcut ahead of that.
"""

import math
import zipfile
from collections.abc import Mapping, Sequence
from io import BytesIO
from urllib.parse import unquote

from src.application.web_reader.publications import PublicationLayout, PublicationResource
from src.application.web_reader.queries.publication_positions import PublicationPosition
from src.domain.common.value_objects.ids import BookId, UserId
from src.infrastructure.web_reader.queries.stored_epub import PublicationQuery, StoredEpub

# Bytes of a reflowable document per position, which is the length every Readium
# toolkit uses (readium/architecture#123). The number is arbitrary and the
# agreement is not: a locator saying "position 42" means nothing unless whoever
# reads it cut the book the same way whoever wrote it did.
POSITION_LENGTH = 1024


class PublicationPositionsQuery(PublicationQuery):
    """Serves a book's position list, computed from its stored EPUB."""

    async def get_publication_positions(
        self, book_id: BookId, user_id: UserId
    ) -> tuple[PublicationPosition, ...] | None:
        """Return the positions of a user's publication, or ``None`` for no such book.

        Raises:
            EbookFileNotFoundError: If the book exists but no EPUB is stored for it.
            InvalidEbookError: If the stored EPUB cannot be parsed.
        """
        return await self._read_publication(book_id, user_id, self._compute_positions)

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
