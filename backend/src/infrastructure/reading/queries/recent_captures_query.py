"""Query adapter for the reader's latest highlights and notes on one timeline.

The two sources keep different clocks. A highlight carries the e-reader's own
wall clock, with no offset to attach it to an instant; a note carries a real
UTC timestamp. They are made comparable by converting the note's into the
reader's zone, which is also what decides the day a note is filed under.

Nothing here decides what counts as a capture: the kinds left out of the feed
come from the ``notes`` domain's own set, and a highlight's effective label is
resolved by ``LabelResolutionService`` rather than re-derived in SQL.
"""

from collections.abc import Sequence
from datetime import datetime as dt
from datetime import timedelta, tzinfo
from typing import Any, cast

from sqlalchemy import ColumnElement, Select, String, case, func, literal, null, select, union_all
from sqlalchemy import cast as sql_cast
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.common.queries.highlight_row import HighlightLabelView
from src.application.reading.queries.recent_captures import CaptureKind, RecentCaptureView
from src.application.reading.services.label_resolution_service import LabelResolutionService
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.notes.entities.note import UNCOUNTED_NOTE_KINDS
from src.domain.reading.services.highlight_style_resolver import ResolvedLabel
from src.infrastructure.library.orm.book_model import Book as BookORM
from src.infrastructure.library.orm.chapter_model import Chapter as ChapterORM
from src.infrastructure.notes.orm.associations import note_books
from src.infrastructure.notes.orm.note_model import Note as NoteORM
from src.infrastructure.reading.orm.highlight_model import Highlight as HighlightORM

CAPTURES_PER_BOOK_PER_DAY = 3
"""How many captures one book may contribute to one day of the feed.

An evening in one book produces a dozen highlights, and uncapped they take
every row a cross-book feed has.
"""

CaptureRow = tuple[
    str,  # kind
    int,  # id
    int,  # book_id
    str,  # book_title
    str | None,  # chapter_name
    str | None,  # title
    str,  # text
    str | None,  # note_kind
    int | None,  # page
    int | None,  # highlight_style_id
    dt,  # captured_at
    int,  # rank within its book and day
    int,  # captures of that book that day
]


def _local_note_time(zone: tzinfo, dialect: str) -> ColumnElement[Any]:
    """The later of a note's two timestamps, read in the reader's zone.

    PostgreSQL converts per row, so historical offsets are right. SQLite has no
    zone database, so its rows shift by the offset in force today — an hour out
    across a DST boundary, on the dialect only tests and local runs use.
    """
    newest = case(
        (NoteORM.updated_at > NoteORM.created_at, NoteORM.updated_at),
        else_=NoteORM.created_at,
    )
    if dialect == "postgresql":
        return func.timezone(getattr(zone, "key", "UTC"), newest)

    offset_hours = (dt.now(zone).utcoffset() or timedelta()).total_seconds() / 3600
    return func.datetime(newest, f"{offset_hours:+f} hours")


def _first_linked_book() -> Select[Any]:
    """Each note's earliest-linked book, which is the one the feed names.

    A note may sit on several books; global search shows the first of them and
    so does this, ordered by when the link was made rather than by book id.
    """
    ranked = select(
        note_books.c.note_id.label("note_id"),
        note_books.c.book_id.label("book_id"),
        func.row_number()
        .over(
            partition_by=note_books.c.note_id,
            order_by=[note_books.c.created_at, note_books.c.book_id],
        )
        .label("rank"),
    ).subquery()
    return select(ranked.c.note_id, ranked.c.book_id).where(ranked.c.rank == 1)


class RecentCapturesQuery:
    """Serves the landing page's capture feed from one union of two selects."""

    def __init__(self, db: AsyncSession, label_resolution_service: LabelResolutionService) -> None:
        self.db = db
        self.label_resolution_service = label_resolution_service

    async def get_recent_captures(
        self, user_id: UserId, zone: tzinfo, limit: int
    ) -> tuple[RecentCaptureView, ...]:
        """Return the reader's newest captures, newest first."""
        rows = await self._fetch_rows(user_id, zone, limit)
        labels = await self._resolve_labels(user_id, rows)
        return tuple(_capture_view(row, labels) for row in rows)

    async def _fetch_rows(self, user_id: UserId, zone: tzinfo, limit: int) -> Sequence[CaptureRow]:
        """Load the newest captures, capped per book per day.

        The cap and the count behind "+N more" come from one window pass over
        the reader's captures, so that count is the day's real remainder rather
        than whatever a page of rows happened to hold.
        """
        dialect = self.db.bind.dialect.name
        captures = union_all(
            self._highlight_leg(user_id), self._note_leg(user_id, zone, dialect)
        ).subquery("captures")

        day = func.date(captures.c.captured_at)
        newest_first = [captures.c.captured_at.desc(), captures.c.id.desc()]
        ranked = select(
            captures,
            func.row_number()
            .over(partition_by=[captures.c.book_id, day], order_by=newest_first)
            .label("rank"),
            func.count().over(partition_by=[captures.c.book_id, day]).label("captures_that_day"),
        ).subquery("ranked")

        stmt = (
            select(ranked)
            .where(ranked.c.rank <= CAPTURES_PER_BOOK_PER_DAY)
            .order_by(ranked.c.captured_at.desc(), ranked.c.id.desc())
            .limit(limit)
        )
        return cast(Sequence[CaptureRow], (await self.db.execute(stmt)).all())

    def _highlight_leg(self, user_id: UserId) -> Select[Any]:
        """The reader's live highlights, on the e-reader's own clock."""
        return (
            select(
                literal(CaptureKind.HIGHLIGHT.value).label("kind"),
                HighlightORM.id.label("id"),
                BookORM.id.label("book_id"),
                BookORM.title.label("book_title"),
                ChapterORM.name.label("chapter_name"),
                sql_cast(null(), String).label("title"),
                HighlightORM.text.label("text"),
                sql_cast(null(), String).label("note_kind"),
                HighlightORM.page.label("page"),
                HighlightORM.highlight_style_id.label("highlight_style_id"),
                HighlightORM.datetime.label("captured_at"),
            )
            .select_from(HighlightORM)
            .join(BookORM, BookORM.id == HighlightORM.book_id)
            .outerjoin(ChapterORM, ChapterORM.id == HighlightORM.chapter_id)
            .where(
                HighlightORM.user_id == user_id.value,
                BookORM.user_id == user_id.value,
                HighlightORM.deleted_at.is_(None),
            )
        )

    def _note_leg(self, user_id: UserId, zone: tzinfo, dialect: str) -> Select[Any]:
        """The reader's notes, on the reader's clock, gists left out.

        A note is filed under its latest edit rather than its creation: a note
        rewritten today is work done today, which is not true of a highlight
        whose selection moved by a word.
        """
        first_book = _first_linked_book().subquery("first_book")
        uncounted = sorted(kind.value for kind in UNCOUNTED_NOTE_KINDS)
        return (
            select(
                literal(CaptureKind.NOTE.value).label("kind"),
                NoteORM.id.label("id"),
                BookORM.id.label("book_id"),
                BookORM.title.label("book_title"),
                sql_cast(null(), String).label("chapter_name"),
                NoteORM.title.label("title"),
                NoteORM.body.label("text"),
                NoteORM.kind.label("note_kind"),
                sql_cast(null(), HighlightORM.page.type).label("page"),
                sql_cast(null(), HighlightORM.highlight_style_id.type).label("highlight_style_id"),
                _local_note_time(zone, dialect).label("captured_at"),
            )
            .select_from(NoteORM)
            .join(first_book, first_book.c.note_id == NoteORM.id)
            .join(BookORM, BookORM.id == first_book.c.book_id)
            .where(
                NoteORM.user_id == user_id.value,
                BookORM.user_id == user_id.value,
                NoteORM.kind.is_(None) | NoteORM.kind.not_in(uncounted),
            )
        )

    async def _resolve_labels(
        self, user_id: UserId, rows: Sequence[CaptureRow]
    ) -> dict[int, ResolvedLabel]:
        """Resolve labels for every book a labelled highlight in the feed came from.

        One call per book rather than one per highlight: a feed of eight rows
        rarely spans more than a handful of books, and the resolution is a
        book-wide map either way.
        """
        book_ids = {
            book_id
            for kind, _, book_id, *_rest, style_id, _at, _rank, _count in rows
            if kind == CaptureKind.HIGHLIGHT.value and style_id is not None
        }
        labels: dict[int, ResolvedLabel] = {}
        for book_id in sorted(book_ids):
            labels.update(
                await self.label_resolution_service.resolve_for_book(user_id, BookId(book_id))
            )
        return labels


def _capture_view(row: CaptureRow, labels: dict[int, ResolvedLabel]) -> RecentCaptureView:
    """Map one union row and its resolved label to the view DTO."""
    (
        kind,
        capture_id,
        book_id,
        book_title,
        chapter_name,
        title,
        text,
        note_kind,
        page,
        style_id,
        captured_at,
        rank,
        captures_that_day,
    ) = row
    resolved = labels.get(style_id) if style_id is not None else None
    hidden = captures_that_day - CAPTURES_PER_BOOK_PER_DAY
    return RecentCaptureView(
        kind=CaptureKind(kind),
        id=capture_id,
        book_id=book_id,
        book_title=book_title,
        chapter_name=chapter_name,
        title=title,
        text=text,
        note_kind=note_kind,
        page=page,
        label=HighlightLabelView(
            highlight_style_id=style_id,
            text=resolved.label if resolved else None,
            ui_color=resolved.ui_color if resolved else None,
        )
        if style_id is not None
        else None,
        captured_at=captured_at,
        day=captured_at.date(),
        more_in_book=hidden if rank == CAPTURES_PER_BOOK_PER_DAY and hidden > 0 else 0,
    )
