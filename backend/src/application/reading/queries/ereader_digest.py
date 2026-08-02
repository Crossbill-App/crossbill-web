"""Read model for the ereader's chapter-digest list.

These are view DTOs, not domain entities: they exist to be rendered and must
never be fed back into a command. See ``docs/adr/0001-read-models-and-query-services.md``.
"""

from dataclasses import dataclass
from datetime import datetime as dt
from typing import Protocol

from src.domain.common.value_objects.ids import UserId


@dataclass(frozen=True)
class EreaderChapterDigestView:
    """Digest for a single chapter, as the device shows it.

    Only question text is exposed -- no AI or user answers -- to keep the
    payload small and preserve the active-recall value on the device.
    """

    chapter_id: int
    chapter_name: str
    chapter_number: int | None
    parent_chapter_name: str | None
    summary: str
    keypoints: tuple[str, ...]
    questions: tuple[str, ...]
    generated_at: dt


class EreaderDigestQueryProtocol(Protocol):
    """Port for reading a book's digest by its client-side id."""

    async def list_for_client_book(
        self, client_book_id: str, user_id: UserId
    ) -> tuple[EreaderChapterDigestView, ...] | None:
        """Return the chapters that have a digest, or ``None`` if no such book."""
        ...
