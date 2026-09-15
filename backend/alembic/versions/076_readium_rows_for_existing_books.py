"""Derive the publication index and the locators of every book already holding an EPUB

The ingest paths #839 and #842 added only cover new writes: a book uploaded
before them has neither a stored publication index nor a Readium Locator on any
of its highlights or reading sessions. EPUBs reach this app from the KOReader
plugin alone, so nobody will re-upload one to trigger the derivation, and the
web reader cannot open a book without it. This fills the backlog once, on
deploy. Every book with an ``ebook_file`` is processed and whatever is already
stored is overwritten -- no reader has a locator yet, so there is nothing to
preserve and no staleness rule to get wrong.

Unlike 037, the only other data migration here, this one imports application
code rather than reimplementing it: the publication index is what the EPUB
parser makes of the archive and a locator is what ``xpoint-cfi`` makes of an
xpointer, and neither can be restated in SQL or in a few lines of Python.

Failure policy: a book whose file is missing, whose archive is unreadable, or
whose xpointers do not parse is logged and skipped, and the run carries on --
that is one book's data being wrong, and the deploy must not hinge on it. A
database error, or a file store that errors rather than answering "not there"
(an S3 refusal or timeout, a local I/O fault), is not contained: it says the
deployment is not what this migration assumed, and it is allowed to fail the
upgrade loudly rather than mark 076 applied with books silently left behind.

Revision ID: 076
Revises: 075
"""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import boto3
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import SQLAlchemyError

from alembic import op
from src.application.web_reader.anchors import Locator
from src.application.web_reader.publications import epub_content_hash
from src.config import EPUBS_DIR, get_settings
from src.domain.common.exceptions import XPointParseError
from src.domain.common.value_objects.xpoint import XPoint, XPointRange
from src.infrastructure.library.services.epub_publication_parser import read_publication
from src.infrastructure.web_reader.mappers.publication_json import publication_to_json
from src.infrastructure.web_reader.services.xpoint_cfi_position_anchor_service import (
    point_locators,
    range_locators,
)

revision: str = "076"
down_revision: str | Sequence[str] | None = "075"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# alembic.ini puts the root logger at WARNING and the ``alembic`` one at INFO,
# so a child of it is what shows up in the deploy log.
logger = logging.getLogger("alembic.readium_backfill")

_JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")

_books = sa.table(
    "books",
    sa.column("id", sa.Integer),
    sa.column("ebook_file", sa.String),
)
_book_publications = sa.table(
    "book_publications",
    sa.column("book_id", sa.Integer),
    sa.column("file_name", sa.String),
    sa.column("content_hash", sa.String),
    sa.column("publication", _JSON),
    sa.column("derived_at", sa.DateTime(timezone=True)),
)
_highlights = sa.table(
    "highlights",
    sa.column("id", sa.Integer),
    sa.column("book_id", sa.Integer),
    sa.column("deleted_at", sa.DateTime(timezone=True)),
    sa.column("start_xpoint", sa.Text),
    sa.column("end_xpoint", sa.Text),
    sa.column("locator", _JSON),
    sa.column("locator_confidence", sa.SmallInteger),
    sa.column("locator_source_hash", sa.String),
)
_reading_sessions = sa.table(
    "reading_sessions",
    sa.column("id", sa.Integer),
    sa.column("book_id", sa.Integer),
    sa.column("start_xpoint", sa.Text),
    sa.column("end_xpoint", sa.Text),
    sa.column("start_locator", _JSON),
    sa.column("end_locator", _JSON),
    sa.column("locator_source_hash", sa.String),
)

_UPDATE_HIGHLIGHT = (
    sa.update(_highlights)
    .where(_highlights.c.id == sa.bindparam("row_id"))
    .values(
        locator=sa.bindparam("row_locator", type_=_JSON),
        locator_confidence=None,
        locator_source_hash=sa.bindparam("row_hash"),
    )
)
_UPDATE_SESSION = (
    sa.update(_reading_sessions)
    .where(_reading_sessions.c.id == sa.bindparam("row_id"))
    .values(
        start_locator=sa.bindparam("row_start", type_=_JSON),
        end_locator=sa.bindparam("row_end", type_=_JSON),
        locator_source_hash=sa.bindparam("row_hash"),
    )
)

# Keyed apart and rejoined as ``session_endpoints`` does it, restated so this
# migration stays frozen.
_START = "start"
_END = "end"

type _Endpoint = tuple[int, str]


@dataclass
class ReadiumBackfillSummary:
    """What one run did, counted for the line it logs at the end.

    ``placed`` means a Locator came back: a row written with a null one against
    the current digest -- this file cannot place that xpointer -- is not counted.
    """

    books_seen: int = 0
    publications_stored: int = 0
    highlights_placed: int = 0
    sessions_placed: int = 0
    epubs_missing: int = 0
    books_failed: int = 0


def upgrade() -> None:
    """Store a publication index and locators for every book that has an EPUB."""
    summary = backfill_readium_rows(op.get_bind(), _epub_reader())
    logger.info("Readium backfill finished: %s", summary)


def downgrade() -> None:
    """No-op: derived data, dropped with its columns by 074's and 073's downgrades."""


def backfill_readium_rows(
    connection: sa.Connection, read_epub: Callable[[str], bytes | None]
) -> ReadiumBackfillSummary:
    """Fill in the publication index and the locators of every book with an EPUB."""
    summary = ReadiumBackfillSummary()
    books = connection.execute(
        sa.select(_books.c.id, _books.c.ebook_file)
        .where(_books.c.ebook_file.is_not(None))
        .order_by(_books.c.id)
    ).all()

    for book_id, file_name in books:
        summary.books_seen += 1
        content = read_epub(file_name)
        if content is None:
            logger.warning("Book %s: no EPUB stored as %r, skipping", book_id, file_name)
            summary.epubs_missing += 1
            continue
        _backfill_book(connection, book_id, file_name, content, summary)

    return summary


def _backfill_book(
    connection: sa.Connection,
    book_id: int,
    file_name: str,
    content: bytes,
    summary: ReadiumBackfillSummary,
) -> None:
    source_hash = epub_content_hash(content)
    failed = False

    try:
        _store_publication(connection, book_id, file_name, content, source_hash)
        summary.publications_stored += 1
    except SQLAlchemyError:
        raise
    except Exception:
        logger.exception("Book %s: could not derive a publication index", book_id)
        failed = True

    # Contained apart from the publication, as the upload path contains them: an
    # archive this parser rejects may still place positions, and the reverse.
    try:
        highlights = _place_highlights(connection, book_id, content, source_hash)
        sessions = _place_sessions(connection, book_id, content, source_hash)
    except SQLAlchemyError:
        raise
    except Exception:
        logger.exception("Book %s: could not derive locators", book_id)
        summary.books_failed += 1
        return

    summary.highlights_placed += highlights
    summary.sessions_placed += sessions
    summary.books_failed += int(failed)
    logger.info("Book %s: %s highlights placed, %s sessions placed", book_id, highlights, sessions)


def _store_publication(
    connection: sa.Connection, book_id: int, file_name: str, content: bytes, source_hash: str
) -> None:
    publication = publication_to_json(read_publication(content))
    values = {
        "file_name": file_name,
        "content_hash": source_hash,
        "publication": publication,
        "derived_at": datetime.now(UTC),
    }
    stored = connection.execute(
        sa.select(_book_publications.c.book_id).where(_book_publications.c.book_id == book_id)
    ).first()
    if stored is None:
        connection.execute(sa.insert(_book_publications).values(book_id=book_id, **values))
    else:
        connection.execute(
            sa.update(_book_publications)
            .where(_book_publications.c.book_id == book_id)
            .values(**values)
        )


def _place_highlights(
    connection: sa.Connection, book_id: int, content: bytes, source_hash: str
) -> int:
    # No user filter: the rows point at this book's file whoever owns them, and
    # each is its owner's to read (R4.2 leaves them where an upload found them).
    rows = connection.execute(
        sa.select(_highlights.c.id, _highlights.c.start_xpoint, _highlights.c.end_xpoint).where(
            _highlights.c.book_id == book_id,
            _highlights.c.deleted_at.is_(None),
            _highlights.c.start_xpoint.is_not(None),
            _highlights.c.end_xpoint.is_not(None),
        )
    ).all()

    ranges: dict[int, XPointRange] = {}
    for row_id, start, end in rows:
        span = _parsed_span(book_id, row_id, start, end)
        if span is not None:
            ranges[row_id] = span
    if not ranges:
        return 0

    locators = range_locators(content, ranges)
    connection.execute(
        _UPDATE_HIGHLIGHT,
        [
            {"row_id": row_id, "row_locator": _payload(locator), "row_hash": source_hash}
            for row_id, locator in locators.items()
        ],
    )
    return sum(1 for locator in locators.values() if locator is not None)


def _place_sessions(
    connection: sa.Connection, book_id: int, content: bytes, source_hash: str
) -> int:
    rows = connection.execute(
        sa.select(
            _reading_sessions.c.id,
            _reading_sessions.c.start_xpoint,
            _reading_sessions.c.end_xpoint,
        ).where(
            _reading_sessions.c.book_id == book_id,
            _reading_sessions.c.start_xpoint.is_not(None),
            _reading_sessions.c.end_xpoint.is_not(None),
        )
    ).all()

    points: dict[_Endpoint, XPoint] = {}
    for row_id, start, end in rows:
        span = _parsed_span(book_id, row_id, start, end)
        if span is not None:
            points[(row_id, _START)] = span.start
            points[(row_id, _END)] = span.end
    if not points:
        return 0

    locators = point_locators(content, points)
    # Keyed off what was asked for rather than what came back, so a session
    # neither of whose endpoints placed still records the digest they failed on.
    placed = {
        row_id: (locators.get((row_id, _START)), locators.get((row_id, _END)))
        for row_id, _ in points
    }
    connection.execute(
        _UPDATE_SESSION,
        [
            {
                "row_id": row_id,
                "row_start": _payload(start),
                "row_end": _payload(end),
                "row_hash": source_hash,
            }
            for row_id, (start, end) in placed.items()
        ],
    )
    return sum(1 for start, end in placed.values() if start is not None or end is not None)


def _parsed_span(book_id: int, row_id: int, start: str, end: str) -> XPointRange | None:
    try:
        return XPointRange.parse(start, end)
    except (XPointParseError, ValueError) as exc:
        logger.warning("Book %s: row %s has an unusable xpointer (%s)", book_id, row_id, exc)
        return None


def _payload(locator: Locator | None) -> dict[str, object] | None:
    return locator.to_dict() if locator is not None else None


def _epub_reader() -> Callable[[str], bytes | None]:
    """Read an EPUB from wherever this deployment keeps them, as the app's repositories do."""
    settings = get_settings()
    if not settings.s3_enabled:
        return _local_epub

    client: Any = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        region_name=settings.S3_REGION,
    )
    bucket = settings.S3_BUCKET_NAME

    def read_from_s3(file_name: str) -> bytes | None:
        try:
            response = client.get_object(Bucket=bucket, Key=f"epubs/{file_name}")
        except client.exceptions.NoSuchKey:
            return None
        data: bytes = response["Body"].read()
        return data

    return read_from_s3


def _local_epub(file_name: str) -> bytes | None:
    path = EPUBS_DIR / file_name
    return path.read_bytes() if path.is_file() else None
