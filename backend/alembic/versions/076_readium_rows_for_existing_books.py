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
xpointer, and neither can be restated in SQL or in a few lines of Python. That
code is imported inside ``_app_code()`` rather than at module level, because
Alembic loads every file in ``alembic/versions`` to build its revision graph:
a top-level ``from src...`` that a later refactor invalidates would break every
``alembic upgrade`` on every database, forever.

Failure policy: nothing here is worth a failed deploy. Everything this migration
derives can be derived again -- a book with no publication index opens in the
web reader with one derived on the spot, and its highlights and reading sessions
gain locators on their next KOReader sync or EPUB upload -- so ``run`` catches
whatever comes out of the backfill, logs it and skips, and a fresh database
simply has no books to backfill. The savepoint it holds is what keeps a failed
statement from aborting Alembic's own transaction on PostgreSQL: whatever the
run wrote is rolled back to it, and the upgrade goes on to record 076 as
applied. Within a run, a book whose file is missing, whose archive is unreadable
or whose xpointers do not parse is logged and skipped, so one book's bad data
does not cost the others theirs.

Revision ID: 076
Revises: 075
"""

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import boto3
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import SQLAlchemyError

from alembic import op

if TYPE_CHECKING:
    from src.application.web_reader.anchors import Locator
    from src.domain.common.value_objects.xpoint import XPoint, XPointRange

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


# Application types are quoted inside the annotations rather than around them:
# Alembic loads a version file without registering it in ``sys.modules``, where
# ``dataclasses`` cannot resolve a field annotated with a string of its own.
@dataclass(frozen=True)
class _Derivation:
    """The application code one run derives with, looked up once so the run is one import."""

    content_hash: Callable[[bytes], str]
    publication_json: Callable[[bytes], dict[str, Any]]
    range_locators: Callable[[bytes, Mapping[int, "XPointRange"]], dict[int, "Locator | None"]]
    point_locators: Callable[
        [bytes, Mapping[_Endpoint, "XPoint"]], dict[_Endpoint, "Locator | None"]
    ]
    parse_range: Callable[[str, str], "XPointRange"]
    parse_error: type[Exception]


def upgrade() -> None:
    """Store a publication index and locators for every book that has an EPUB."""
    run(op.get_bind())


def downgrade() -> None:
    """No-op: derived data, dropped with its columns by 074's and 073's downgrades."""


def run(connection: sa.Connection) -> ReadiumBackfillSummary | None:
    """Back every book up to date, or log what stopped it and leave them as they were."""
    try:
        with connection.begin_nested():
            summary = backfill_readium_rows(connection, _epub_reader(), _app_code())
    except Exception:
        logger.exception(
            "Readium backfill skipped: a book opens in the web reader with its manifest "
            "derived on first open, and its highlights and reading sessions gain locators "
            "on their next KOReader sync or EPUB upload"
        )
        return None

    logger.info("Readium backfill finished: %s", summary)
    return summary


def backfill_readium_rows(
    connection: sa.Connection,
    read_epub: Callable[[str], bytes | None],
    code: _Derivation,
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
        _backfill_book(connection, book_id, file_name, content, code, summary)

    return summary


def _backfill_book(
    connection: sa.Connection,
    book_id: int,
    file_name: str,
    content: bytes,
    code: _Derivation,
    summary: ReadiumBackfillSummary,
) -> None:
    source_hash = code.content_hash(content)
    failed = False

    try:
        _store_publication(connection, book_id, file_name, content, source_hash, code)
        summary.publications_stored += 1
    # A failed statement has already aborted the transaction on PostgreSQL, so it
    # goes straight to ``run``: contained here, every later book would fail too.
    except SQLAlchemyError:
        raise
    except Exception:
        logger.exception("Book %s: could not derive a publication index", book_id)
        failed = True

    # Contained apart from the publication, as the upload path contains them: an
    # archive this parser rejects may still place positions, and the reverse.
    try:
        highlights = _place_highlights(connection, book_id, content, source_hash, code)
        sessions = _place_sessions(connection, book_id, content, source_hash, code)
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
    connection: sa.Connection,
    book_id: int,
    file_name: str,
    content: bytes,
    source_hash: str,
    code: _Derivation,
) -> None:
    values = {
        "file_name": file_name,
        "content_hash": source_hash,
        "publication": code.publication_json(content),
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
    connection: sa.Connection, book_id: int, content: bytes, source_hash: str, code: _Derivation
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
        span = _parsed_span(book_id, row_id, start, end, code)
        if span is not None:
            ranges[row_id] = span
    if not ranges:
        return 0

    locators = code.range_locators(content, ranges)
    connection.execute(
        _UPDATE_HIGHLIGHT,
        [
            {"row_id": row_id, "row_locator": _payload(locator), "row_hash": source_hash}
            for row_id, locator in locators.items()
        ],
    )
    return sum(1 for locator in locators.values() if locator is not None)


def _place_sessions(
    connection: sa.Connection, book_id: int, content: bytes, source_hash: str, code: _Derivation
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
        span = _parsed_span(book_id, row_id, start, end, code)
        if span is not None:
            points[(row_id, _START)] = span.start
            points[(row_id, _END)] = span.end
    if not points:
        return 0

    locators = code.point_locators(content, points)
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


def _parsed_span(
    book_id: int, row_id: int, start: str, end: str, code: _Derivation
) -> "XPointRange | None":
    try:
        return code.parse_range(start, end)
    except (code.parse_error, ValueError) as exc:
        logger.warning("Book %s: row %s has an unusable xpointer (%s)", book_id, row_id, exc)
        return None


def _payload(locator: "Locator | None") -> dict[str, object] | None:
    return locator.to_dict() if locator is not None else None


def _app_code() -> _Derivation:
    """Look up the application code this migration derives with, importing it as late as possible."""
    from src.application.web_reader.publications import epub_content_hash  # noqa: PLC0415
    from src.domain.common.exceptions import XPointParseError  # noqa: PLC0415
    from src.domain.common.value_objects.xpoint import XPointRange  # noqa: PLC0415
    from src.infrastructure.library.services.epub_publication_parser import (  # noqa: PLC0415
        read_publication,
    )
    from src.infrastructure.web_reader.mappers.publication_json import (  # noqa: PLC0415
        publication_to_json,
    )
    from src.infrastructure.web_reader.services.xpoint_cfi_position_anchor_service import (  # noqa: PLC0415
        point_locators,
        range_locators,
    )

    return _Derivation(
        content_hash=epub_content_hash,
        publication_json=lambda content: publication_to_json(read_publication(content)),
        range_locators=range_locators,
        point_locators=point_locators,
        parse_range=XPointRange.parse,
        parse_error=XPointParseError,
    )


def _epub_reader() -> Callable[[str], bytes | None]:
    """Read an EPUB from wherever this deployment keeps them, as the app's repositories do."""
    from src.config import get_settings  # noqa: PLC0415

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
    from src.config import EPUBS_DIR  # noqa: PLC0415

    path = EPUBS_DIR / file_name
    return path.read_bytes() if path.is_file() else None
