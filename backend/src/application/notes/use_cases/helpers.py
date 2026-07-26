"""Shared helpers for note use cases.

``parse_note_kind`` is also used by the note read use cases: converting the
API's kind string is the same job on both sides, and a query importing from the
command package is the allowed direction of the ``queries-are-dead-ends``
contract.
"""

from collections.abc import Callable

from src.application.library.protocols.chapter_repository import ChapterRepositoryProtocol
from src.application.reading.protocols.highlight_repository import HighlightRepositoryProtocol
from src.application.tagging.protocols.tag_repository import (
    TagRepositoryProtocol,
)
from src.domain.common.exceptions import EntityNotFoundError, ValidationError
from src.domain.common.value_objects import UserId
from src.domain.notes.entities.note import NoteKind
from src.domain.notes.exceptions import NoteLinkBookMismatchError
from src.domain.reading.exceptions import (
    ChapterNotFoundError,
    HighlightNotFoundError,
)
from src.domain.tagging.exceptions import TagNotFoundError


def parse_note_kind(kind: str | None) -> NoteKind | None:
    """Convert an API kind string to NoteKind, or raise ValidationError."""
    if kind is None:
        return None
    try:
        return NoteKind(kind)
    except ValueError as exc:
        raise ValidationError(f"Invalid note kind: {kind}") from exc


async def validate_link_targets(
    user_id: UserId,
    allowed_book_ids: set[int],
    chapter_ids: list[int],
    highlight_ids: list[int],
    tag_ids: list[int],
    chapter_repository: ChapterRepositoryProtocol,
    highlight_repository: HighlightRepositoryProtocol,
    tag_repository: TagRepositoryProtocol,
) -> None:
    """Validate that every linked entity exists, is owned, and belongs to a linked book.

    Each entity kind is fetched with a single bulk query; a requested id missing
    from the result was either not found or not owned by the user.
    """
    chapters = await chapter_repository.find_by_ids(chapter_ids, user_id)
    _check_links(
        chapter_ids,
        {chapter.id.value: chapter.book_id.value for chapter in chapters},
        allowed_book_ids,
        ChapterNotFoundError,
        "Chapter",
    )

    highlights = await highlight_repository.find_by_ids(highlight_ids, user_id)
    _check_links(
        highlight_ids,
        {highlight.id.value: highlight.book_id.value for highlight in highlights},
        allowed_book_ids,
        HighlightNotFoundError,
        "Highlight",
    )

    tags = await tag_repository.find_by_ids(tag_ids, user_id)
    _check_links(
        tag_ids,
        {tag.id.value: tag.book_id.value for tag in tags},
        allowed_book_ids,
        TagNotFoundError,
        "Tag",
    )


def _check_links(
    requested_ids: list[int],
    book_id_by_id: dict[int, int],
    allowed_book_ids: set[int],
    not_found_error: Callable[[int], EntityNotFoundError],
    entity_type: str,
) -> None:
    """Raise NotFound for any missing id, or a book mismatch for a wrong book."""
    for requested_id in requested_ids:
        book_id = book_id_by_id.get(requested_id)
        if book_id is None:
            raise not_found_error(requested_id)
        if book_id not in allowed_book_ids:
            raise NoteLinkBookMismatchError(entity_type, requested_id)

