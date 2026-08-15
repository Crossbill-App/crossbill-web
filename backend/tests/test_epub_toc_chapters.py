"""Tests for EPUB ToC chapter creation and update logic.

This test suite focuses on the complex logic in EbookUploadService._save_chapters_from_toc,
which handles:
- Creating new chapters from ToC
- Updating existing chapters
- Handling hierarchical parent-child relationships
- Managing duplicate chapter names (same name under different parents)
- Detecting true duplicates (same name and parent in ToC)
"""

# type: ignore - Testing protected methods and accessing DB fields that Pyright doesn't recognize

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src import models
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.library.entities.chapter import TocChapter
from src.infrastructure.library.repositories.chapter_repository import ChapterRepository
from tests.conftest import create_test_book


def toc_ch(
    name: str,
    num: int,
    parent: str | None = None,
    start: str | None = None,
    end: str | None = None,
    parent_index: int | None = None,
) -> TocChapter:
    """Shorthand for constructing TocChapter in tests."""
    return TocChapter(
        name=name,
        chapter_number=num,
        parent_name=parent,
        start_xpoint=start,
        end_xpoint=end,
        parent_index=parent_index,
    )


@pytest.fixture
async def chapter_repo(db_session: AsyncSession) -> ChapterRepository:
    """Create a ChapterRepository instance with test database session."""
    return ChapterRepository(db=db_session)


@pytest.fixture
async def test_book_for_toc(db_session: AsyncSession) -> models.Book:
    """Create a test book for ToC testing."""
    return await create_test_book(
        db_session=db_session,
        user_id=1,
        title="ToC Test Book",
        author="Test Author",
    )


class TestSimpleChapterCreation:
    """Test basic chapter creation without hierarchy."""

    async def test_create_single_chapter(
        self,
        chapter_repo: ChapterRepository,
        test_book_for_toc: models.Book,
        db_session: AsyncSession,
    ) -> None:
        """Test creating a single chapter from ToC."""
        chapters = [toc_ch("Introduction", 1)]

        created_count = await chapter_repo.sync_chapters_from_toc(
            book_id=BookId(test_book_for_toc.id), user_id=UserId(1), chapters=chapters
        )

        assert created_count == 1
        result = await db_session.execute(
            select(models.Chapter).filter_by(book_id=test_book_for_toc.id)
        )
        db_chapters = result.scalars().all()
        assert len(db_chapters) == 1
        assert db_chapters[0].name == "Introduction"
        assert db_chapters[0].chapter_number == 1
        assert db_chapters[0].parent_id is None

    async def test_create_multiple_chapters(
        self,
        chapter_repo: ChapterRepository,
        test_book_for_toc: models.Book,
        db_session: AsyncSession,
    ):
        """Test creating multiple chapters from ToC."""
        chapters = [
            toc_ch("Chapter 1", 1),
            toc_ch("Chapter 2", 2),
            toc_ch("Chapter 3", 3),
        ]

        created_count = await chapter_repo.sync_chapters_from_toc(
            book_id=BookId(test_book_for_toc.id), user_id=UserId(1), chapters=chapters
        )

        assert created_count == 3
        result = await db_session.execute(
            select(models.Chapter)
            .filter_by(book_id=test_book_for_toc.id)
            .order_by(models.Chapter.chapter_number)
        )
        db_chapters = result.scalars().all()
        assert len(db_chapters) == 3
        assert [ch.name for ch in db_chapters] == ["Chapter 1", "Chapter 2", "Chapter 3"]
        assert all(ch.parent_id is None for ch in db_chapters)

    async def test_empty_chapters_list(
        self,
        chapter_repo: ChapterRepository,
        test_book_for_toc: models.Book,
        db_session: AsyncSession,
    ):
        """Test handling empty chapters list."""
        chapters: list[TocChapter] = []

        created_count = await chapter_repo.sync_chapters_from_toc(
            book_id=BookId(test_book_for_toc.id), user_id=UserId(1), chapters=chapters
        )

        assert created_count == 0
        result = await db_session.execute(
            select(models.Chapter).filter_by(book_id=test_book_for_toc.id)
        )
        db_chapters = result.scalars().all()
        assert len(db_chapters) == 0


class TestHierarchicalChapters:
    """Test hierarchical parent-child chapter relationships."""

    async def test_simple_parent_child(
        self,
        chapter_repo: ChapterRepository,
        test_book_for_toc: models.Book,
        db_session: AsyncSession,
    ):
        """Test creating parent chapter with child chapters."""
        chapters = [
            toc_ch("Part I", 1),
            toc_ch("Chapter 1", 2, "Part I"),
            toc_ch("Chapter 2", 3, "Part I"),
        ]

        created_count = await chapter_repo.sync_chapters_from_toc(
            book_id=BookId(test_book_for_toc.id), user_id=UserId(1), chapters=chapters
        )

        assert created_count == 3
        result = await db_session.execute(
            select(models.Chapter)
            .filter_by(book_id=test_book_for_toc.id)
            .order_by(models.Chapter.chapter_number)
        )
        db_chapters = result.scalars().all()
        assert len(db_chapters) == 3

        part1 = db_chapters[0]
        chapter1 = db_chapters[1]
        chapter2 = db_chapters[2]

        assert part1.name == "Part I"
        assert part1.parent_id is None

        assert chapter1.name == "Chapter 1"
        assert chapter1.parent_id == part1.id

        assert chapter2.name == "Chapter 2"
        assert chapter2.parent_id == part1.id

    async def test_multiple_parent_levels(
        self,
        chapter_repo: ChapterRepository,
        test_book_for_toc: models.Book,
        db_session: AsyncSession,
    ):
        """Test creating multiple levels of parent-child hierarchy."""
        chapters = [
            toc_ch("Part I", 1),
            toc_ch("Chapter 1", 2, "Part I"),
            toc_ch("Section 1.1", 3, "Chapter 1"),
            toc_ch("Section 1.2", 4, "Chapter 1"),
            toc_ch("Chapter 2", 5, "Part I"),
        ]

        created_count = await chapter_repo.sync_chapters_from_toc(
            book_id=BookId(test_book_for_toc.id), user_id=UserId(1), chapters=chapters
        )

        assert created_count == 5
        result = await db_session.execute(
            select(models.Chapter)
            .filter_by(book_id=test_book_for_toc.id)
            .order_by(models.Chapter.chapter_number)
        )
        db_chapters = result.scalars().all()

        part1, chapter1, section11, section12, chapter2 = db_chapters

        assert part1.parent_id is None
        assert chapter1.parent_id == part1.id
        assert section11.parent_id == chapter1.id
        assert section12.parent_id == chapter1.id
        assert chapter2.parent_id == part1.id


class TestDuplicateChapterNames:
    """Test handling chapters with duplicate names.

    With the constraint (book_id, parent_id, name), chapters can have the same name
    as long as they have different parents.
    """

    async def test_duplicate_names_different_parents_allowed(
        self,
        chapter_repo: ChapterRepository,
        test_book_for_toc: models.Book,
        db_session: AsyncSession,
    ):
        """Test that chapters with same name under different parents are both created.

        This is the main bug fix - "Harjoitukset" under Part I and Part II should
        both be created as separate chapters.
        """
        chapters = [
            toc_ch("Part I", 1),
            toc_ch("Harjoitukset", 2, "Part I"),
            toc_ch("Part II", 3),
            toc_ch("Harjoitukset", 4, "Part II"),
        ]

        created_count = await chapter_repo.sync_chapters_from_toc(
            book_id=BookId(test_book_for_toc.id), user_id=UserId(1), chapters=chapters
        )

        assert created_count == 4
        result = await db_session.execute(
            select(models.Chapter)
            .filter_by(book_id=test_book_for_toc.id)
            .order_by(models.Chapter.chapter_number)
        )
        db_chapters = result.scalars().all()
        assert len(db_chapters) == 4

        part1, harjoitukset1, part2, harjoitukset2 = db_chapters

        # Both "Harjoitukset" chapters should exist
        assert harjoitukset1.name == "Harjoitukset"
        assert harjoitukset1.parent_id == part1.id
        assert harjoitukset1.chapter_number == 2

        assert harjoitukset2.name == "Harjoitukset"
        assert harjoitukset2.parent_id == part2.id
        assert harjoitukset2.chapter_number == 4

        # They should have different IDs
        assert harjoitukset1.id != harjoitukset2.id

    async def test_duplicate_names_at_root_level_skipped(
        self,
        chapter_repo: ChapterRepository,
        test_book_for_toc: models.Book,
        db_session: AsyncSession,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that duplicate root-level chapters (both parent_id=None) are skipped.

        With the (book_id, parent_id, name) constraint, two root chapters with same name
        have the same (name, parent_id) key, so they're treated as duplicates.
        """
        chapters = [
            toc_ch("Preface", 1),
            toc_ch("Preface", 2),  # Duplicate at root level
        ]

        created_count = await chapter_repo.sync_chapters_from_toc(
            book_id=BookId(test_book_for_toc.id), user_id=UserId(1), chapters=chapters
        )

        # Only one created, duplicate skipped
        assert created_count == 1
        result = await db_session.execute(
            select(models.Chapter).filter_by(book_id=test_book_for_toc.id)
        )
        db_chapters = result.scalars().all()
        assert len(db_chapters) == 1
        assert db_chapters[0].name == "Preface"
        assert db_chapters[0].parent_id is None

        # Should log a warning about the duplicate
        assert "Duplicate chapter 'Preface' in ToC with same parent" in caplog.text

    async def test_true_duplicate_in_toc_skipped(
        self,
        chapter_repo: ChapterRepository,
        test_book_for_toc: models.Book,
        db_session: AsyncSession,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that true duplicates (same name and parent in ToC) are skipped.

        This would indicate a malformed ToC where the same chapter appears twice
        under the same parent.
        """
        chapters = [
            toc_ch("Part I", 1),
            toc_ch("Chapter 1", 2, "Part I"),
            toc_ch("Chapter 1", 3, "Part I"),  # True duplicate - same name and parent
        ]

        created_count = await chapter_repo.sync_chapters_from_toc(
            book_id=BookId(test_book_for_toc.id), user_id=UserId(1), chapters=chapters
        )

        # Only 2 chapters created (duplicate skipped)
        assert created_count == 2
        result = await db_session.execute(
            select(models.Chapter)
            .filter_by(book_id=test_book_for_toc.id)
            .order_by(models.Chapter.chapter_number)
        )
        db_chapters = result.scalars().all()
        assert len(db_chapters) == 2
        assert db_chapters[0].name == "Part I"
        assert db_chapters[1].name == "Chapter 1"

        # Should log a warning about the duplicate
        assert "Duplicate chapter 'Chapter 1' in ToC with same parent" in caplog.text


class TestUpdatingExistingChapters:
    """Test updating existing chapters when re-uploading ToC."""

    async def test_update_chapter_number(
        self,
        chapter_repo: ChapterRepository,
        test_book_for_toc: models.Book,
        db_session: AsyncSession,
    ):
        """Test updating chapter_number for existing chapter."""
        # Create initial chapter
        existing_chapter = models.Chapter(
            book_id=test_book_for_toc.id,
            name="Chapter 1",
            chapter_number=1,
            parent_id=None,
        )
        db_session.add(existing_chapter)
        await db_session.commit()
        chapter_id = existing_chapter.id

        # Re-upload with different chapter number
        chapters = [toc_ch("Chapter 1", 5)]

        created_count = await chapter_repo.sync_chapters_from_toc(
            book_id=BookId(test_book_for_toc.id), user_id=UserId(1), chapters=chapters
        )

        assert created_count == 0  # No new chapters created
        await db_session.refresh(existing_chapter)
        assert existing_chapter.id == chapter_id  # Same chapter
        assert existing_chapter.chapter_number == 5  # Updated

    async def test_update_parent_id(
        self,
        chapter_repo: ChapterRepository,
        test_book_for_toc: models.Book,
        db_session: AsyncSession,
    ):
        """Test updating parent_id for existing chapter when they share the same parent.

        NOTE: This only works when the parent_id doesn't change. If parent_id changes,
        the unique key (book_id, parent_id, name) changes, and the current logic
        creates a new chapter instead of updating. This is a known limitation.
        """
        # Create initial chapters with the same parent
        parent = models.Chapter(
            book_id=test_book_for_toc.id, name="Part I", chapter_number=1, parent_id=None
        )
        db_session.add(parent)
        await db_session.commit()
        await db_session.refresh(parent)

        child = models.Chapter(
            book_id=test_book_for_toc.id,
            name="Chapter 1",
            chapter_number=2,
            parent_id=parent.id,  # Initially HAS parent
        )
        db_session.add(child)
        await db_session.commit()
        child_id = child.id

        # Re-upload with same parent but different chapter number
        chapters = [
            toc_ch("Part I", 1),
            toc_ch("Chapter 1", 5, "Part I"),  # Same parent, different number
        ]

        created_count = await chapter_repo.sync_chapters_from_toc(
            book_id=BookId(test_book_for_toc.id), user_id=UserId(1), chapters=chapters
        )

        assert created_count == 0  # No new chapters
        await db_session.refresh(child)
        assert child.id == child_id  # Same chapter
        assert child.parent_id == parent.id  # Parent unchanged
        assert child.chapter_number == 5  # Updated

    async def test_mixed_create_and_update(
        self,
        chapter_repo: ChapterRepository,
        test_book_for_toc: models.Book,
        db_session: AsyncSession,
    ):
        """Test creating new chapters while updating existing ones."""
        # Create initial chapter
        existing = models.Chapter(
            book_id=test_book_for_toc.id,
            name="Chapter 1",
            chapter_number=1,
            parent_id=None,
        )
        db_session.add(existing)
        await db_session.commit()
        existing_id = existing.id

        # Upload with existing chapter (different number) and new chapters
        chapters = [
            toc_ch("Chapter 1", 5),  # Exists - update
            toc_ch("Chapter 2", 6),  # New - create
            toc_ch("Chapter 3", 7),  # New - create
        ]

        created_count = await chapter_repo.sync_chapters_from_toc(
            book_id=BookId(test_book_for_toc.id), user_id=UserId(1), chapters=chapters
        )

        assert created_count == 2  # Only new chapters counted
        result = await db_session.execute(
            select(models.Chapter)
            .filter_by(book_id=test_book_for_toc.id)
            .order_by(models.Chapter.chapter_number)
        )
        db_chapters = result.scalars().all()
        assert len(db_chapters) == 3
        assert db_chapters[0].id == existing_id  # Same chapter
        assert db_chapters[0].chapter_number == 5  # Updated

    async def test_reupload_with_duplicate_chapter_names(
        self,
        chapter_repo: ChapterRepository,
        test_book_for_toc: models.Book,
        db_session: AsyncSession,
    ):
        """Test re-uploading EPUB TOC when book already has duplicate chapter names under different parents.

        This is a regression test for the bug where get_by_names() returned a dict keyed by name,
        causing data loss when multiple chapters had the same name but different parent_ids.

        The bug manifested as:
        - First upload: SUCCESS (chapters created correctly)
        - Second upload: FAILURE (unique constraint violation trying to re-insert "missing" chapter)
        """
        # Initial upload: Create chapters with duplicate names under different parents
        initial_chapters = [
            toc_ch("Part I", 1),
            toc_ch("Harjoitukset", 2, "Part I"),
            toc_ch("Part II", 3),
            toc_ch("Harjoitukset", 4, "Part II"),
        ]

        created_count = await chapter_repo.sync_chapters_from_toc(
            book_id=BookId(test_book_for_toc.id), user_id=UserId(1), chapters=initial_chapters
        )
        assert created_count == 4

        # Re-upload the same TOC (simulating re-uploading the EPUB file via API)
        # This should detect all existing chapters and update them, not try to create duplicates
        created_count_2 = await chapter_repo.sync_chapters_from_toc(
            book_id=BookId(test_book_for_toc.id), user_id=UserId(1), chapters=initial_chapters
        )

        # Should create 0 new chapters (all already exist)
        assert created_count_2 == 0

        # Should still have exactly 4 chapters in database
        result = await db_session.execute(
            select(models.Chapter)
            .filter_by(book_id=test_book_for_toc.id)
            .order_by(models.Chapter.chapter_number)
        )
        db_chapters = result.scalars().all()
        assert len(db_chapters) == 4

        # Verify both "Harjoitukset" chapters still exist with correct parents
        part1, harjoitukset1, part2, harjoitukset2 = db_chapters

        assert harjoitukset1.name == "Harjoitukset"
        assert harjoitukset1.parent_id == part1.id
        assert harjoitukset1.chapter_number == 2

        assert harjoitukset2.name == "Harjoitukset"
        assert harjoitukset2.parent_id == part2.id
        assert harjoitukset2.chapter_number == 4

        # Verify they are distinct chapters
        assert harjoitukset1.id != harjoitukset2.id


class TestRepeatedSyncWithRepeatedNames:
    """Test that re-syncing a TOC whose names repeat across levels is idempotent.

    The KOReader plugin re-uploads the EPUB on every sync, so sync_chapters_from_toc
    runs repeatedly over the same TOC. Resolving parents by bare name made run 2 pick a
    different parent row than run 1 (last-write-wins over a repeated name), so the
    (name, parent_id) keys missed and a whole subtree was created a second time. Every
    duplicate chapter_number then breaks the plugin's digest cache and misroutes
    highlights, which key chapters by number.
    """

    @staticmethod
    def _repeated_name_toc() -> list[TocChapter]:
        """A TOC repeating a parent name ("Luku") and a child name ("Yhteenveto").

        Osa I / Luku / {Yhteenveto, Itsetuntemus}, Osa II / Luku / Yhteenveto.
        """
        return [
            toc_ch("Osa I", 1, start="/body/DocFragment[1]/body"),
            toc_ch("Luku", 2, "Osa I", "/body/DocFragment[2]/body", parent_index=0),
            toc_ch("Yhteenveto", 3, "Luku", "/body/DocFragment[3]/body", parent_index=1),
            toc_ch("Itsetuntemus", 4, "Luku", "/body/DocFragment[4]/body", parent_index=1),
            toc_ch("Osa II", 5, start="/body/DocFragment[5]/body"),
            toc_ch("Luku", 6, "Osa II", "/body/DocFragment[6]/body", parent_index=4),
            toc_ch("Yhteenveto", 7, "Luku", "/body/DocFragment[7]/body", parent_index=5),
        ]

    async def test_second_sync_creates_no_duplicates(
        self,
        chapter_repo: ChapterRepository,
        test_book_for_toc: models.Book,
        db_session: AsyncSession,
    ) -> None:
        toc = self._repeated_name_toc()

        first_count = await chapter_repo.sync_chapters_from_toc(
            book_id=BookId(test_book_for_toc.id), user_id=UserId(1), chapters=toc
        )
        assert first_count == 7

        result = await db_session.execute(
            select(models.Chapter)
            .filter_by(book_id=test_book_for_toc.id)
            .order_by(models.Chapter.chapter_number)
        )
        ids_after_first = [ch.id for ch in result.scalars().all()]

        second_count = await chapter_repo.sync_chapters_from_toc(
            book_id=BookId(test_book_for_toc.id), user_id=UserId(1), chapters=toc
        )

        assert second_count == 0

        result = await db_session.execute(
            select(models.Chapter)
            .filter_by(book_id=test_book_for_toc.id)
            .order_by(models.Chapter.chapter_number)
        )
        db_chapters = result.scalars().all()

        # Same rows as after the first sync -- nothing created, nothing orphaned
        assert [ch.id for ch in db_chapters] == ids_after_first

        # chapter_number is an identity for the ereader plugin: it must stay unique
        numbers = [ch.chapter_number for ch in db_chapters]
        assert numbers == [1, 2, 3, 4, 5, 6, 7]
        pairs = [(ch.name, ch.chapter_number) for ch in db_chapters]
        assert len(set(pairs)) == len(pairs)

        osa1, luku1, yhteenveto1, itsetuntemus, osa2, luku2, yhteenveto2 = db_chapters
        assert luku1.parent_id == osa1.id
        assert luku2.parent_id == osa2.id
        assert yhteenveto1.parent_id == luku1.id
        assert itsetuntemus.parent_id == luku1.id
        assert yhteenveto2.parent_id == luku2.id

    async def test_repeated_names_are_placed_under_the_indexed_parent(
        self,
        chapter_repo: ChapterRepository,
        test_book_for_toc: models.Book,
        db_session: AsyncSession,
    ) -> None:
        """parent_index wins over parent_name when the name is ambiguous.

        Both "Luku" sections carry parent_name "Osa I", but the indexes say otherwise;
        the rows must follow the indexes.
        """
        toc = [
            toc_ch("Osa I", 1),
            toc_ch("Osa II", 2),
            toc_ch("Luku", 3, "Osa I", parent_index=0),
            toc_ch("Luku", 4, "Osa I", parent_index=1),
        ]

        created = await chapter_repo.sync_chapters_from_toc(
            book_id=BookId(test_book_for_toc.id), user_id=UserId(1), chapters=toc
        )

        assert created == 4
        result = await db_session.execute(
            select(models.Chapter)
            .filter_by(book_id=test_book_for_toc.id)
            .order_by(models.Chapter.chapter_number)
        )
        osa1, osa2, luku_a, luku_b = result.scalars().all()
        assert luku_a.parent_id == osa1.id
        assert luku_b.parent_id == osa2.id


class TestLegacyFlatChapterMigration:
    """Test migration of legacy flat chapters (pre-hierarchy) during EPUB upload.

    Books in production may have chapters created before hierarchical TOC support
    was added. These legacy chapters have parent_id=None and no xpoints. When an
    EPUB is uploaded, the TOC produces chapters with parent_id set and xpoints,
    which would fail to match legacy chapters by (name, parent_id) key, causing
    duplicates and orphaning highlights attached to the old chapters.
    """

    async def test_legacy_flat_chapters_updated_in_place(
        self,
        chapter_repo: ChapterRepository,
        test_book_for_toc: models.Book,
        db_session: AsyncSession,
    ) -> None:
        """Legacy flat chapters are updated in-place when EPUB TOC provides hierarchy.

        Ensures chapter IDs are preserved (so highlight foreign keys remain valid),
        parent_id and xpoints are populated, and no duplicates are created.
        """
        # Create legacy flat chapters (as they existed before hierarchy was added)
        legacy_part = models.Chapter(
            book_id=test_book_for_toc.id,
            name="Part I",
            chapter_number=1,
            parent_id=None,
        )
        legacy_ch1 = models.Chapter(
            book_id=test_book_for_toc.id,
            name="Chapter 1",
            chapter_number=2,
            parent_id=None,  # Legacy: no parent
            start_xpoint=None,  # Legacy: no xpoints
            end_xpoint=None,
        )
        legacy_ch2 = models.Chapter(
            book_id=test_book_for_toc.id,
            name="Chapter 2",
            chapter_number=3,
            parent_id=None,
            start_xpoint=None,
            end_xpoint=None,
        )
        db_session.add_all([legacy_part, legacy_ch1, legacy_ch2])
        await db_session.commit()

        # Record original IDs to verify in-place updates
        part_id = legacy_part.id
        ch1_id = legacy_ch1.id
        ch2_id = legacy_ch2.id

        # Upload EPUB with hierarchical TOC referencing same chapter names
        toc_chapters = [
            toc_ch("Part I", 1, start="/body/DocFragment[2]/body", end="/body/DocFragment[3]/body"),
            toc_ch(
                "Chapter 1", 2, "Part I", "/body/DocFragment[3]/body", "/body/DocFragment[4]/body"
            ),
            toc_ch(
                "Chapter 2", 3, "Part I", "/body/DocFragment[4]/body", "/body/DocFragment[5]/body"
            ),
        ]

        created_count = await chapter_repo.sync_chapters_from_toc(
            book_id=BookId(test_book_for_toc.id), user_id=UserId(1), chapters=toc_chapters
        )

        # No new chapters should be created -- all matched to legacy chapters
        assert created_count == 0

        result = await db_session.execute(
            select(models.Chapter)
            .filter_by(book_id=test_book_for_toc.id)
            .order_by(models.Chapter.chapter_number)
        )
        db_chapters = result.scalars().all()

        # Total count should equal TOC size (no duplicates)
        assert len(db_chapters) == 3

        part, ch1, ch2 = db_chapters

        # IDs preserved (highlight foreign keys still valid)
        assert part.id == part_id
        assert ch1.id == ch1_id
        assert ch2.id == ch2_id

        # Part I remains root (parent_id=None in both legacy and TOC)
        assert part.parent_id is None
        assert part.start_xpoint == "/body/DocFragment[2]/body"

        # Children now have parent_id set
        assert ch1.parent_id == part_id
        assert ch1.start_xpoint == "/body/DocFragment[3]/body"
        assert ch1.end_xpoint == "/body/DocFragment[4]/body"

        assert ch2.parent_id == part_id
        assert ch2.start_xpoint == "/body/DocFragment[4]/body"
        assert ch2.end_xpoint == "/body/DocFragment[5]/body"

    async def test_legacy_migration_with_duplicate_names_under_different_parents(
        self,
        chapter_repo: ChapterRepository,
        test_book_for_toc: models.Book,
        db_session: AsyncSession,
    ) -> None:
        """Legacy flat chapters with duplicate names are matched correctly.

        When multiple legacy chapters share a name (e.g., "Exercises" under different
        parts), only the first one should match via legacy fallback. The second one
        would need a new chapter since the legacy key is consumed after the first match.
        """
        # Create legacy flat chapters with duplicate name
        legacy_part1 = models.Chapter(
            book_id=test_book_for_toc.id, name="Part I", chapter_number=1, parent_id=None
        )
        legacy_exercises = models.Chapter(
            book_id=test_book_for_toc.id,
            name="Exercises",
            chapter_number=2,
            parent_id=None,
        )
        legacy_part2 = models.Chapter(
            book_id=test_book_for_toc.id, name="Part II", chapter_number=3, parent_id=None
        )
        db_session.add_all([legacy_part1, legacy_exercises, legacy_part2])
        await db_session.commit()

        exercises_id = legacy_exercises.id

        # TOC has "Exercises" under two different parents
        toc_chapters = [
            toc_ch("Part I", 1),
            toc_ch("Exercises", 2, "Part I"),
            toc_ch("Part II", 3),
            toc_ch("Exercises", 4, "Part II"),
        ]

        created_count = await chapter_repo.sync_chapters_from_toc(
            book_id=BookId(test_book_for_toc.id), user_id=UserId(1), chapters=toc_chapters
        )

        # First "Exercises" matched legacy, second one is new
        assert created_count == 1

        result = await db_session.execute(
            select(models.Chapter)
            .filter_by(book_id=test_book_for_toc.id)
            .order_by(models.Chapter.chapter_number)
        )
        db_chapters = result.scalars().all()

        assert len(db_chapters) == 4

        part1, exercises1, part2, exercises2 = db_chapters

        # First "Exercises" should be the legacy chapter updated in-place
        assert exercises1.id == exercises_id
        assert exercises1.parent_id == part1.id

        # Second "Exercises" is a new chapter
        assert exercises2.id != exercises_id
        assert exercises2.parent_id == part2.id


class TestEdgeCases:
    """Test edge cases and potential issues in the ToC logic."""

    async def test_duplicate_parent_names_correct_assignment(
        self,
        chapter_repo: ChapterRepository,
        test_book_for_toc: models.Book,
        db_session: AsyncSession,
    ):
        """Test that duplicate parent names work correctly with the fixed logic.

        This test verifies that when two parent chapters have the same name
        (e.g., "Introduction" under Part I and "Introduction" under Part II),
        child chapters are assigned to the correct parent.

        With the chapter_by_name_and_parent tracking, this edge case is handled correctly.
        The child chapters reference the correct parent even though multiple parents
        have the same name.

        Example:
            Part I
              Introduction (id=10)
                Chapter 1 (should have parent_id=10) correct
            Part II
              Introduction (id=20)
                Chapter 1 (should have parent_id=20) correct
        """
        chapters = [
            toc_ch("Part I", 1),
            toc_ch("Introduction", 2, "Part I"),
            toc_ch("Chapter 1", 3, "Introduction"),
            toc_ch("Part II", 4),
            toc_ch("Introduction", 5, "Part II"),
            toc_ch("Chapter 1", 6, "Introduction"),
        ]

        created_count = await chapter_repo.sync_chapters_from_toc(
            book_id=BookId(test_book_for_toc.id), user_id=UserId(1), chapters=chapters
        )

        assert created_count == 6
        result = await db_session.execute(
            select(models.Chapter)
            .filter_by(book_id=test_book_for_toc.id)
            .order_by(models.Chapter.chapter_number)
        )
        db_chapters = result.scalars().all()

        part1, intro1, chapter1_under_intro1, part2, intro2, chapter1_under_intro2 = db_chapters

        # Verify parent structure
        assert intro1.name == "Introduction"
        assert intro1.parent_id == part1.id

        assert intro2.name == "Introduction"
        assert intro2.parent_id == part2.id

        # Verify children are correctly assigned to their respective parents
        # Chapter 1 (number 3) should have intro1 as parent
        assert chapter1_under_intro1.parent_id == intro1.id

        # Chapter 1 (number 6) should have intro2 as parent
        assert chapter1_under_intro2.parent_id == intro2.id

    async def test_parent_referenced_before_definition(
        self,
        chapter_repo: ChapterRepository,
        test_book_for_toc: models.Book,
        db_session: AsyncSession,
    ):
        """Test that parent chapters must come before children in ToC.

        This tests the assumption that ToC is ordered (parents before children).
        If a child references a parent that hasn't been processed yet, parent_id
        will be None.
        """
        chapters = [
            toc_ch("Chapter 1", 1, "Part I"),
            toc_ch("Part I", 2),
        ]

        created_count = await chapter_repo.sync_chapters_from_toc(
            book_id=BookId(test_book_for_toc.id), user_id=UserId(1), chapters=chapters
        )

        assert created_count == 2
        result = await db_session.execute(
            select(models.Chapter)
            .filter_by(book_id=test_book_for_toc.id)
            .order_by(models.Chapter.chapter_number)
        )
        db_chapters = result.scalars().all()

        chapter1, part1 = db_chapters

        # Chapter 1 won't have parent_id set because Part I wasn't processed yet
        assert chapter1.parent_id is None
        assert part1.parent_id is None

    async def test_nonexistent_parent_name(
        self,
        chapter_repo: ChapterRepository,
        test_book_for_toc: models.Book,
        db_session: AsyncSession,
    ):
        """Test handling of parent_name that doesn't exist in ToC."""
        chapters = [toc_ch("Chapter 1", 1, "Part I")]

        created_count = await chapter_repo.sync_chapters_from_toc(
            book_id=BookId(test_book_for_toc.id), user_id=UserId(1), chapters=chapters
        )

        assert created_count == 1
        result = await db_session.execute(
            select(models.Chapter).filter_by(book_id=test_book_for_toc.id)
        )
        db_chapters = result.scalars().all()
        assert len(db_chapters) == 1
        # Parent doesn't exist, so parent_id is None
        assert db_chapters[0].parent_id is None
