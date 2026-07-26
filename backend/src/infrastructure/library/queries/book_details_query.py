"""Query adapter for the book-details view.

Reads map ORM rows straight to view DTOs: no aggregates are loaded and no
domain entities are built. Queries select, join, filter, order and group --
they never decide anything. The one rule-derived value on this page (a
highlight's effective label) is delegated to ``LabelResolutionService`` rather
than re-encoded in SQL.
"""

from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, noload

from src.application.library.queries.book_details import (
    BookDetailsView,
    BookmarkView,
    ChapterWithHighlightsView,
    FlashcardRef,
    HighlightLabelView,
    HighlightView,
    TagGroupRef,
    TagRef,
)
from src.application.reading.services.label_resolution_service import LabelResolutionService
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.common.value_objects.position import Position
from src.domain.library.entities.book import ReadingStage
from src.domain.reading.services.highlight_style_resolver import ResolvedLabel
from src.infrastructure.learning.orm.flashcard_model import Flashcard as FlashcardORM
from src.infrastructure.library.orm.book_model import Book as BookORM
from src.infrastructure.library.orm.chapter_model import Chapter as ChapterORM
from src.infrastructure.notes.orm.associations import note_tags
from src.infrastructure.reading.orm.associations import highlight_tags
from src.infrastructure.reading.orm.bookmark_model import Bookmark as BookmarkORM
from src.infrastructure.reading.orm.highlight_model import Highlight as HighlightORM
from src.infrastructure.reading.orm.reading_session_model import ReadingSession as ReadingSessionORM
from src.infrastructure.tagging.orm.tag_group_model import TagGroup as TagGroupORM
from src.infrastructure.tagging.orm.tag_model import Tag as TagORM


def _position(raw: list[int] | None) -> Position | None:
    """Read a stored ``[index, char_index]`` pair back into a Position."""
    return Position.from_json(raw) if raw else None


class BookDetailsQuery:
    """Serves the book-details read model from purpose-built selects."""

    def __init__(self, db: AsyncSession, label_resolution_service: LabelResolutionService) -> None:
        self.db = db
        self.label_resolution_service = label_resolution_service

    async def get_book_details(self, book_id: BookId, user_id: UserId) -> BookDetailsView | None:
        """Return the view for a user's book, or ``None`` when they have no such book."""
        book_row = await self._fetch_book(book_id, user_id)
        if book_row is None:
            return None
        book, reading_position = book_row

        labels = await self.label_resolution_service.resolve_for_book(user_id, book_id)

        return BookDetailsView(
            id=book.id,
            client_book_id=book.client_book_id,
            title=book.title,
            author=book.author,
            isbn=book.isbn,
            cover_file=book.cover_file,
            cover_blurhash=book.cover_blurhash,
            description=book.description,
            language=book.language,
            page_count=book.page_count,
            reading_stage=ReadingStage(book.reading_stage) if book.reading_stage else None,
            tags=await self._fetch_tags(book_id, user_id),
            tag_groups=await self._fetch_tag_groups(book_id),
            bookmarks=await self._fetch_bookmarks(book_id),
            book_flashcards=await self._fetch_book_flashcards(book_id, user_id),
            chapters=await self._fetch_chapters(book_id, user_id, labels),
            reading_position=reading_position,
            end_position=_position(book.end_position),
            created_at=book.created_at,
            updated_at=book.updated_at,
            last_viewed=book.last_viewed,
        )

    async def _fetch_book(
        self, book_id: BookId, user_id: UserId
    ) -> tuple[BookORM, Position | None] | None:
        """Load the book row plus the end position of its latest reading session."""
        latest_position = (
            select(ReadingSessionORM.end_position)
            .where(
                ReadingSessionORM.book_id == book_id.value,
                ReadingSessionORM.user_id == user_id.value,
            )
            .order_by(ReadingSessionORM.start_time.desc())
            .limit(1)
            .scalar_subquery()
        )
        stmt = (
            select(BookORM, latest_position)
            # Book.tag_groups is lazy="selectin"; the view loads groups itself.
            .options(noload(BookORM.tag_groups))
            .where(
                BookORM.id == book_id.value,
                BookORM.user_id == user_id.value,
            )
        )
        row = (await self.db.execute(stmt)).first()
        if row is None:
            return None
        return row[0], _position(row[1])

    async def _fetch_tags(self, book_id: BookId, user_id: UserId) -> tuple[TagRef, ...]:
        """Load the book's tags that are in active use, ordered by name."""
        has_active_highlight = (
            select(highlight_tags.c.tag_id)
            .join(HighlightORM, HighlightORM.id == highlight_tags.c.highlight_id)
            .where(
                highlight_tags.c.tag_id == TagORM.id,
                HighlightORM.deleted_at.is_(None),
            )
            .exists()
        )
        has_note = select(note_tags.c.tag_id).where(note_tags.c.tag_id == TagORM.id).exists()
        stmt = (
            select(TagORM.id, TagORM.name, TagORM.tag_group_id)
            .where(
                TagORM.book_id == book_id.value,
                TagORM.user_id == user_id.value,
                or_(has_active_highlight, has_note),
            )
            .order_by(TagORM.name)
        )
        rows = (await self.db.execute(stmt)).all()
        return tuple(
            TagRef(id=row.id, name=row.name, tag_group_id=row.tag_group_id) for row in rows
        )

    async def _fetch_tag_groups(self, book_id: BookId) -> tuple[TagGroupRef, ...]:
        """Load the book's tag groups, ordered by name."""
        stmt = (
            select(TagGroupORM.id, TagGroupORM.name)
            .where(TagGroupORM.book_id == book_id.value)
            .order_by(TagGroupORM.name)
        )
        rows = (await self.db.execute(stmt)).all()
        return tuple(TagGroupRef(id=row.id, name=row.name) for row in rows)

    async def _fetch_bookmarks(self, book_id: BookId) -> tuple[BookmarkView, ...]:
        """Load the book's bookmarks, newest first."""
        stmt = (
            select(BookmarkORM)
            .where(BookmarkORM.book_id == book_id.value)
            .order_by(BookmarkORM.created_at.desc())
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return tuple(
            BookmarkView(
                id=row.id,
                book_id=row.book_id,
                highlight_id=row.highlight_id,
                created_at=row.created_at,
            )
            for row in rows
        )

    async def _fetch_book_flashcards(
        self, book_id: BookId, user_id: UserId
    ) -> tuple[FlashcardRef, ...]:
        """Load the flashcards that hang off the book itself rather than a highlight."""
        stmt = (
            select(FlashcardORM)
            .where(
                FlashcardORM.book_id == book_id.value,
                FlashcardORM.user_id == user_id.value,
                FlashcardORM.highlight_id.is_(None),
            )
            .order_by(FlashcardORM.created_at.desc())
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return tuple(_flashcard_ref(row) for row in rows)

    async def _fetch_chapters(
        self,
        book_id: BookId,
        user_id: UserId,
        labels: dict[int, ResolvedLabel],
    ) -> tuple[ChapterWithHighlightsView, ...]:
        """Load every chapter of the book with the highlights that sit in it.

        Chapters without highlights are kept, and highlight groups whose chapter
        is not among the book's chapters are appended at the end.
        """
        chapters = await self._fetch_chapter_rows(book_id, user_id)
        highlights = await self._fetch_highlight_rows(book_id, user_id)

        grouped: dict[int, list[HighlightORM]] = defaultdict(list)
        orphan_chapters: dict[int, ChapterORM] = {}
        chapters_by_id = {chapter.id: chapter for chapter in chapters}
        for highlight in highlights:
            chapter_id = highlight.chapter_id
            if chapter_id is None:
                continue
            grouped[chapter_id].append(highlight)
            if chapter_id not in chapters_by_id and highlight.chapter is not None:
                orphan_chapters[chapter_id] = highlight.chapter

        ordered = list(chapters) + sorted(
            orphan_chapters.values(), key=lambda chapter: chapter.chapter_number or 0
        )
        return tuple(
            _chapter_view(chapter, grouped.get(chapter.id, []), labels) for chapter in ordered
        )

    async def _fetch_chapter_rows(self, book_id: BookId, user_id: UserId) -> Sequence[ChapterORM]:
        """Load every chapter of the book, ordered by chapter number."""
        stmt = (
            select(ChapterORM)
            .join(BookORM, BookORM.id == ChapterORM.book_id)
            .where(
                BookORM.id == book_id.value,
                BookORM.user_id == user_id.value,
            )
            .order_by(ChapterORM.chapter_number)
        )
        return (await self.db.execute(stmt)).scalars().all()

    async def _fetch_highlight_rows(
        self, book_id: BookId, user_id: UserId
    ) -> Sequence[HighlightORM]:
        """Load the book's live highlights with their chapter, tags and flashcards."""
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
                HighlightORM.book_id == book_id.value,
                HighlightORM.user_id == user_id.value,
                HighlightORM.deleted_at.is_(None),
            )
            .order_by(HighlightORM.created_at.desc())
        )
        return (await self.db.execute(stmt)).unique().scalars().all()


def _flashcard_ref(row: FlashcardORM) -> FlashcardRef:
    """Map a flashcard row to its view DTO."""
    return FlashcardRef(
        id=row.id,
        user_id=row.user_id,
        book_id=row.book_id,
        highlight_id=row.highlight_id,
        chapter_id=row.chapter_id,
        question=row.question,
        answer=row.answer,
    )


def _highlight_view(row: HighlightORM, labels: dict[int, ResolvedLabel]) -> HighlightView:
    """Map a highlight row and its eagerly loaded relations to the view DTO."""
    style_id = row.highlight_style_id
    resolved = labels.get(style_id) if style_id is not None else None
    return HighlightView(
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
        tags=tuple(
            TagRef(id=tag.id, name=tag.name, tag_group_id=tag.tag_group_id) for tag in row.tags
        ),
        flashcards=tuple(_flashcard_ref(card) for card in row.flashcards),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _chapter_view(
    chapter: ChapterORM,
    highlights: list[HighlightORM],
    labels: dict[int, ResolvedLabel],
) -> ChapterWithHighlightsView:
    """Map a chapter row and its highlights to the view DTO."""
    ordered = sorted(highlights, key=lambda row: row.page or row.id)
    return ChapterWithHighlightsView(
        id=chapter.id,
        name=chapter.name,
        chapter_number=chapter.chapter_number,
        parent_id=chapter.parent_id,
        start_position=_position(chapter.start_position),
        highlights=tuple(_highlight_view(row, labels) for row in ordered),
        created_at=chapter.created_at,
        updated_at=chapter.updated_at,
    )
