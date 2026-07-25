"""Tests for hydrate_note_links."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from src.application.notes.use_cases.dtos import NoteWithLinkedEntities
from src.application.notes.use_cases.helpers import hydrate_note_links
from src.domain.common.value_objects import (
    BookId,
    ChapterId,
    HighlightId,
    NoteId,
    TagId,
    UserId,
)
from src.domain.library.entities.chapter import Chapter
from src.domain.notes.entities.note import Note
from src.domain.reading.entities.highlight import Highlight
from src.domain.reading.entities.tag import Tag

USER_ID = UserId(1)
BOOK_ID = BookId(10)


def _note(
    note_id: int = 1,
    chapter_ids: list[int] | None = None,
    highlight_ids: list[int] | None = None,
    tag_ids: list[int] | None = None,
) -> Note:
    now = datetime.now(UTC)
    return Note.create_with_id(
        id=NoteId(note_id),
        user_id=USER_ID,
        title=f"Note {note_id}",
        body="",
        kind=None,
        created_at=now,
        updated_at=now,
        book_ids=[BOOK_ID.value],
        chapter_ids=chapter_ids or [],
        highlight_ids=highlight_ids or [],
        tag_ids=tag_ids or [],
    )


def _chapter(chapter_id: int) -> Chapter:
    return Chapter(
        id=ChapterId(chapter_id),
        book_id=BOOK_ID,
        name=f"Chapter {chapter_id}",
        created_at=datetime.now(UTC),
    )


def _highlight(highlight_id: int, deleted_at: datetime | None = None) -> Highlight:
    return Highlight(
        id=HighlightId(highlight_id),
        user_id=USER_ID,
        book_id=BOOK_ID,
        text=f"Highlight {highlight_id}",
        deleted_at=deleted_at,
    )


def _tag(tag_id: int) -> Tag:
    return Tag(id=TagId(tag_id), user_id=USER_ID, book_id=BOOK_ID, name=f"Tag {tag_id}")


@pytest.fixture
def chapter_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.find_by_ids.return_value = []
    return repo


@pytest.fixture
def highlight_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.find_by_ids.return_value = []
    return repo


@pytest.fixture
def tag_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.find_by_ids.return_value = []
    return repo


async def _hydrate(
    notes: list[Note],
    chapter_repo: AsyncMock,
    highlight_repo: AsyncMock,
    tag_repo: AsyncMock,
) -> list[NoteWithLinkedEntities]:
    return await hydrate_note_links(
        notes,
        USER_ID,
        chapter_repository=chapter_repo,
        highlight_repository=highlight_repo,
        tag_repository=tag_repo,
    )


class TestHydrateNoteLinks:
    async def test_returns_empty_without_querying_when_no_notes(
        self,
        chapter_repo: AsyncMock,
        highlight_repo: AsyncMock,
        tag_repo: AsyncMock,
    ) -> None:
        result = await _hydrate([], chapter_repo, highlight_repo, tag_repo)

        assert result == []
        chapter_repo.find_by_ids.assert_not_awaited()
        highlight_repo.find_by_ids.assert_not_awaited()
        tag_repo.find_by_ids.assert_not_awaited()

    async def test_resolves_links_for_a_single_note(
        self,
        chapter_repo: AsyncMock,
        highlight_repo: AsyncMock,
        tag_repo: AsyncMock,
    ) -> None:
        chapter_repo.find_by_ids.return_value = [_chapter(5)]
        highlight_repo.find_by_ids.return_value = [_highlight(7)]
        tag_repo.find_by_ids.return_value = [_tag(9)]
        note = _note(chapter_ids=[5], highlight_ids=[7], tag_ids=[9])

        (result,) = await _hydrate([note], chapter_repo, highlight_repo, tag_repo)

        assert result.note is note
        assert [c.id.value for c in result.chapters] == [5]
        assert [h.id.value for h in result.highlights] == [7]
        assert [t.id.value for t in result.tags] == [9]

    async def test_leaves_flashcards_empty(
        self,
        chapter_repo: AsyncMock,
        highlight_repo: AsyncMock,
        tag_repo: AsyncMock,
    ) -> None:
        (result,) = await _hydrate([_note()], chapter_repo, highlight_repo, tag_repo)

        assert result.flashcards == []

    async def test_keeps_the_order_of_the_notes_own_id_lists(
        self,
        chapter_repo: AsyncMock,
        highlight_repo: AsyncMock,
        tag_repo: AsyncMock,
    ) -> None:
        # Repositories are free to return rows in any order; the note's own
        # ordering is what the response must preserve.
        chapter_repo.find_by_ids.return_value = [_chapter(1), _chapter(2), _chapter(3)]
        note = _note(chapter_ids=[3, 1, 2])

        (result,) = await _hydrate([note], chapter_repo, highlight_repo, tag_repo)

        assert [c.id.value for c in result.chapters] == [3, 1, 2]

    async def test_drops_ids_the_repositories_do_not_return(
        self,
        chapter_repo: AsyncMock,
        highlight_repo: AsyncMock,
        tag_repo: AsyncMock,
    ) -> None:
        chapter_repo.find_by_ids.return_value = [_chapter(1)]
        tag_repo.find_by_ids.return_value = []
        note = _note(chapter_ids=[1, 2], tag_ids=[8])

        (result,) = await _hydrate([note], chapter_repo, highlight_repo, tag_repo)

        assert [c.id.value for c in result.chapters] == [1]
        assert result.tags == []

    async def test_drops_soft_deleted_highlights(
        self,
        chapter_repo: AsyncMock,
        highlight_repo: AsyncMock,
        tag_repo: AsyncMock,
    ) -> None:
        highlight_repo.find_by_ids.return_value = [
            _highlight(1),
            _highlight(2, deleted_at=datetime.now(UTC)),
        ]
        note = _note(highlight_ids=[1, 2])

        (result,) = await _hydrate([note], chapter_repo, highlight_repo, tag_repo)

        assert [h.id.value for h in result.highlights] == [1]

    async def test_queries_each_repository_once_for_many_notes(
        self,
        chapter_repo: AsyncMock,
        highlight_repo: AsyncMock,
        tag_repo: AsyncMock,
    ) -> None:
        chapter_repo.find_by_ids.return_value = [_chapter(1), _chapter(2), _chapter(3)]
        notes = [
            _note(1, chapter_ids=[1], highlight_ids=[1], tag_ids=[1]),
            _note(2, chapter_ids=[2], highlight_ids=[2], tag_ids=[2]),
            _note(3, chapter_ids=[3], highlight_ids=[3], tag_ids=[3]),
        ]

        results = await _hydrate(notes, chapter_repo, highlight_repo, tag_repo)

        assert len(results) == 3
        assert chapter_repo.find_by_ids.await_count == 1
        assert highlight_repo.find_by_ids.await_count == 1
        assert tag_repo.find_by_ids.await_count == 1

    async def test_requests_the_union_of_ids_across_notes(
        self,
        chapter_repo: AsyncMock,
        highlight_repo: AsyncMock,
        tag_repo: AsyncMock,
    ) -> None:
        notes = [_note(1, chapter_ids=[1, 2]), _note(2, chapter_ids=[2, 3])]

        await _hydrate(notes, chapter_repo, highlight_repo, tag_repo)

        requested_ids, requested_user = chapter_repo.find_by_ids.await_args.args
        assert sorted(requested_ids) == [1, 2, 3]
        assert requested_user == USER_ID

    async def test_returns_results_in_the_order_of_the_input_notes(
        self,
        chapter_repo: AsyncMock,
        highlight_repo: AsyncMock,
        tag_repo: AsyncMock,
    ) -> None:
        notes = [_note(3), _note(1), _note(2)]

        results = await _hydrate(notes, chapter_repo, highlight_repo, tag_repo)

        assert [r.note.id.value for r in results] == [3, 1, 2]
