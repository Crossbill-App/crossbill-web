"""Query adapter for the in-book highlight search.

The old path loaded each match as a full ``Highlight`` aggregate plus the
book, chapter, tags and flashcards behind it, mapped every one through a
domain entity, and then threw the book away. Here the rows go straight to view
DTOs. The one rule-derived value on the page -- a highlight's effective label
-- is delegated to ``LabelResolutionService`` rather than re-encoded in SQL.

Grouping stays in Python rather than becoming a ``GROUP BY``: the ordering the
search returns (relevance on PostgreSQL) has to survive into the chapter
buckets, and the chapter rows arrive on the join anyway.
"""

from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, noload

from src.application.reading.queries.highlight_search import (
    BookHighlightSearchView,
    FlashcardRef,
    HighlightLabelView,
    SearchChapterView,
    SearchHighlightView,
    TagRef,
)
from src.application.reading.services.label_resolution_service import LabelResolutionService
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.reading.services.highlight_style_resolver import ResolvedLabel
from src.infrastructure.common.sql import LIKE_ESCAPE_CHAR, escape_like_pattern
from src.infrastructure.learning.orm.flashcard_model import Flashcard as FlashcardORM
from src.infrastructure.library.orm.book_model import Book as BookORM
from src.infrastructure.library.orm.chapter_model import Chapter as ChapterORM
from src.infrastructure.reading.orm.highlight_model import Highlight as HighlightORM
from src.infrastructure.tagging.orm.tag_model import Tag as TagORM


class HighlightSearchQuery:
    """Serves the in-book highlight search from one select plus label resolution."""

    def __init__(self, db: AsyncSession, label_resolution_service: LabelResolutionService) -> None:
        self.db = db
        self.label_resolution_service = label_resolution_service

    async def search_in_book(
        self, book_id: BookId, user_id: UserId, search_text: str, limit: int = 100
    ) -> BookHighlightSearchView | None:
        """Return the matches grouped by chapter, or ``None`` if the user has no such book."""
        if not await self._owns_book(book_id, user_id):
            return None

        matches = await self._fetch_matches(book_id, user_id, search_text, limit)
        labels = await self.label_resolution_service.resolve_for_book(user_id, book_id)
        chapters = _group_by_chapter(matches, labels)
        return BookHighlightSearchView(
            chapters=chapters,
            total=sum(len(chapter.highlights) for chapter in chapters),
        )

    async def _owns_book(self, book_id: BookId, user_id: UserId) -> bool:
        """Report whether the book exists and belongs to the user."""
        stmt = select(BookORM.id).where(
            BookORM.id == book_id.value,
            BookORM.user_id == user_id.value,
        )
        return (await self.db.execute(stmt)).first() is not None

    async def _fetch_matches(
        self, book_id: BookId, user_id: UserId, search_text: str, limit: int
    ) -> Sequence[HighlightORM]:
        """Load the book's live highlights matching the search, most relevant first.

        PostgreSQL ranks by its full-text index; SQLite has none, so tests and
        local runs fall back to a LIKE scan ordered by recency.
        """
        is_postgresql = self.db.bind.dialect.name == "postgresql"
        stmt = (
            select(HighlightORM)
            .options(
                joinedload(HighlightORM.chapter),
                joinedload(HighlightORM.tags),
                joinedload(HighlightORM.flashcards),
                # Highlight.reading_sessions is lazy="selectin" and unused here.
                noload(HighlightORM.reading_sessions),
            )
            .where(
                HighlightORM.user_id == user_id.value,
                HighlightORM.book_id == book_id.value,
                HighlightORM.deleted_at.is_(None),
            )
        )

        if search_text and is_postgresql:
            search_query = func.plainto_tsquery("english", search_text)
            stmt = stmt.where(HighlightORM.text_search_vector.op("@@")(search_query)).order_by(
                func.ts_rank(HighlightORM.text_search_vector, search_query).desc()
            )
        else:
            if search_text:
                escaped = escape_like_pattern(search_text)
                stmt = stmt.where(HighlightORM.text.ilike(f"%{escaped}%", escape=LIKE_ESCAPE_CHAR))
            stmt = stmt.order_by(HighlightORM.created_at.desc())

        return (await self.db.execute(stmt.limit(limit))).unique().scalars().all()


def _group_by_chapter(
    matches: Sequence[HighlightORM], labels: dict[int, ResolvedLabel]
) -> tuple[SearchChapterView, ...]:
    """Bucket matches into their chapters, ordered by chapter number.

    A match whose chapter is unknown is dropped: the response lists chapters,
    and there is no chapter to list it under.
    """
    grouped: dict[int, list[HighlightORM]] = defaultdict(list)
    chapters: dict[int, ChapterORM] = {}
    for row in matches:
        if row.chapter is None:
            continue
        grouped[row.chapter.id].append(row)
        chapters[row.chapter.id] = row.chapter

    ordered = sorted(chapters.values(), key=lambda chapter: chapter.chapter_number or 0)
    return tuple(_chapter_view(chapter, grouped[chapter.id], labels) for chapter in ordered)


def _chapter_view(
    chapter: ChapterORM,
    matches: list[HighlightORM],
    labels: dict[int, ResolvedLabel],
) -> SearchChapterView:
    """Map a chapter and the matches inside it to the view DTO."""
    ordered = sorted(matches, key=lambda row: row.page or row.id)
    return SearchChapterView(
        id=chapter.id,
        name=chapter.name,
        chapter_number=chapter.chapter_number,
        highlights=tuple(_highlight_view(row, labels) for row in ordered),
        created_at=chapter.created_at,
        updated_at=chapter.updated_at,
    )


def _highlight_view(row: HighlightORM, labels: dict[int, ResolvedLabel]) -> SearchHighlightView:
    """Map a matched highlight and its eagerly loaded relations to the view DTO."""
    style_id = row.highlight_style_id
    resolved = labels.get(style_id) if style_id is not None else None
    return SearchHighlightView(
        id=row.id,
        book_id=row.book_id,
        chapter_id=row.chapter_id,
        chapter_name=row.chapter.name if row.chapter else None,
        chapter_number=row.chapter.chapter_number if row.chapter else None,
        text=row.text,
        page=row.page,
        datetime=row.datetime,
        label=HighlightLabelView(
            highlight_style_id=style_id,
            text=resolved.label if resolved else None,
            ui_color=resolved.ui_color if resolved else None,
        )
        if style_id is not None
        else None,
        tags=tuple(_tag_ref(tag) for tag in row.tags),
        flashcards=tuple(_flashcard_ref(card) for card in row.flashcards),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _tag_ref(row: TagORM) -> TagRef:
    """Map a tag row to its view DTO."""
    return TagRef(id=row.id, name=row.name, tag_group_id=row.tag_group_id)


def _flashcard_ref(row: FlashcardORM) -> FlashcardRef:
    """Map a flashcard row to its view DTO."""
    return FlashcardRef(
        id=row.id,
        user_id=row.user_id,
        book_id=row.book_id,
        highlight_id=row.highlight_id,
        chapter_id=row.chapter_id,
        note_id=row.note_id,
        question=row.question,
        answer=row.answer,
    )
