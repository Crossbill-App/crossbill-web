"""A publication's Readium position list, computed from its stored index.

A *position* is a synthetic page: an EPUB's reflowable documents have no pages
of their own, so Readium cuts each one into :data:`POSITION_LENGTH`-byte pieces
and calls each piece a position. That is a convention rather than a derivation
-- what matters is only that a publication is cut the same way every time it is
read -- so the arithmetic follows the Readium toolkits' recipe (go-toolkit
``pkg/parser/epub/positions_service.go``, kotlin-toolkit
``EpubPositionsService``) rather than a better one of our own invention:

- ``position`` is 1-based and runs on across resources;
- ``progression`` is ``i / count`` for the ``i``-th position of its own
  resource, zero-based, so every resource opens at ``0.0``;
- ``totalProgression`` is ``(position - 1) / total``, so the book opens at
  ``0.0`` and its last position sits below ``1.0`` rather than at it.

**Two deliberate divergences from go-toolkit**, both narrowing what a number can
depend on:

*Length is the resource's uncompressed size, not its compressed one.* The Go
toolkit measures the stored (deflated) length, which it documents as the
historical Adobe RMSDK-compatible strategy. Compressed length is a property of
whoever built the zip rather than of the book: recompressing an EPUB, or storing
one member and deflating the next, silently renumbers positions that highlights
and reading progress are expressed against. The uncompressed size is what the
parser already recorded on the stored publication index, so cutting a book up is
arithmetic over a row that has been read anyway.

*Layout is read per reading-order item, not per publication.* Go decides once
for the whole book from the package metadata; our parser resolves
``rendition:layout`` per spine item and the manifest publishes it that way, so a
mixed-layout publication would otherwise be numbered against a layout the
manifest denies.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from src.application.web_reader.publications import PublicationLayout, PublicationResource
from src.domain.library.exceptions import InvalidEbookError

# Bytes of a reflowable document per position, which is the length every Readium
# toolkit uses (readium/architecture#123). The number is arbitrary and the
# agreement is not: a locator saying "position 42" means nothing unless whoever
# reads it cut the book the same way whoever wrote it did.
POSITION_LENGTH = 1024

# The most positions one publication may be cut into.
#
# This is the one web-reader response a small file can inflate for free:
# everywhere else the bytes have to exist, while a position list is arithmetic
# over sizes the archive merely *declares*. The upstream guard is
# `MAX_PUBLICATION_UNCOMPRESSED_BYTES`
# (2 GiB, `infrastructure/library/services/epub_publication_parser.py`), which
# admits a publication declaring two million positions -- each of which becomes
# a dataclass, then a Pydantic model, then a JSON object on the way out.
#
# The size is derived from the upload limit rather than picked. An EPUB arrives
# as at most the 50 MiB `MAX_EBOOK_SIZE` an upload may be, and XHTML deflates at
# roughly four to one, so four times the upload cap is a generous ceiling on the
# markup an honest reading order can hold. For scale: the longest novel ever
# published runs to about 4 MB of text, some four thousand positions.
MAX_PUBLICATION_POSITIONS = 4 * 50 * 1024 * 1024 // POSITION_LENGTH


@dataclass(frozen=True)
class PublicationPosition:
    """One position in a publication, as a Readium Locator carries it.

    Attributes:
        href: The resource this position falls in, as a path inside the EPUB
            container -- the same form
            :class:`~src.application.web_reader.publications.PublicationResource`
            uses, not a served URL.
        media_type: The media type the publication declares for that resource.
        position: The position's 1-based number, counted across the whole
            publication rather than restarted per resource.
        progression: How far into its own resource this position begins, in
            ``[0, 1)``.
        total_progression: How far into the whole publication it begins, in
            ``[0, 1)``.
    """

    href: str
    media_type: str
    position: int
    progression: float
    total_progression: float


def position_list(reading_order: Sequence[PublicationResource]) -> tuple[PublicationPosition, ...]:
    """Cut a reading order into positions, the way the Readium toolkits cut one.

    Raises:
        InvalidEbookError: If the reading order declares more than
            :data:`MAX_PUBLICATION_POSITIONS` positions.
    """
    counts = [_position_count(resource) for resource in reading_order]
    total = sum(counts)
    # Counted before anything is built, which is the whole difference between a
    # refusal and an outage: `counts` is one integer per reading-order item, so
    # the sum is free, while the list it describes is an object per kilobyte of
    # a book that may not exist. Judging the list after building it would pay
    # the cost this exists to refuse.
    if total > MAX_PUBLICATION_POSITIONS:
        raise InvalidEbookError(
            f"declares {total} positions, over the {MAX_PUBLICATION_POSITIONS} limit",
            "epub",
        )

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


def _position_count(resource: PublicationResource) -> int:
    # A fixed-layout resource is a spread the author typeset, so cutting it up
    # would number places that are all visible at once. A resource worth zero
    # positions would be unreachable in a list addressed by position.
    if resource.layout is PublicationLayout.FIXED:
        return 1
    return max(1, math.ceil(resource.size / POSITION_LENGTH))
