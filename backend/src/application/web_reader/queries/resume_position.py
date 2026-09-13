"""Read model for "where should the web reader open this book?".

Not the same question as "what did the browser last store". Somebody who read
three chapters on their e-reader last night has no browser position for those
chapters at all, so both stored places are weighed and the later one wins.

Nothing is derived here. R4.2 stores a locator beside every reading session, so
this read serves a stored one or says the place could not be placed.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from src.application.web_reader.anchors import Locator
from src.domain.common.value_objects.ids import BookId, UserId


class ResumeSource(StrEnum):
    """Which reader the position being resumed from came from."""

    WEB = "web"
    KOREADER = "koreader"


@dataclass(frozen=True)
class BrowserPosition:
    """Where the browser last stored this reader, as it sent it.

    The locator is the navigator's own document, so its href names this API's
    resource URL rather than a path inside the container.
    """

    locator: Mapping[str, Any]
    source_hash: str
    recorded_at: datetime


@dataclass(frozen=True)
class DevicePosition:
    """Where the latest reading session another device wrote ended.

    ``locator`` is ``None`` where nothing was ever derived for that end -- the
    session still says the reader was somewhere, which is why it is a candidate.
    """

    locator: Locator | None
    source_hash: str | None
    ended_at: datetime


@dataclass(frozen=True)
class ResumeCandidates:
    """Both stored places, beside the publication digest they are judged against.

    ``publication_hash`` is ``None`` when the book has no publication row --
    distinct from the port answering ``None``, which means no such book.
    """

    publication_hash: str | None
    browser: BrowserPosition | None
    device: DevicePosition | None


class ResumePositionQueryProtocol(Protocol):
    """Port reading both stored places and the publication digest beside them."""

    async def resume_candidates(self, book_id: BookId, user_id: UserId) -> ResumeCandidates | None:
        """Return the book's stored places, or ``None`` if the user has no such book."""
        ...


@dataclass(frozen=True)
class ResumePosition:
    """Where to open a book, and what that answer rests on.

    Three states, and the reader treats each differently: no source at all means
    the book has been read nowhere and opens at the beginning silently; a source
    with a locator means navigate there; a source without one means a place was
    recorded and cannot be placed in the EPUB we now hold, so the book opens at
    the beginning *and says so*.

    The two locator fields are two different things rather than one said twice.
    ``browser_locator`` is the navigator's own stored document, in the coordinates
    the manifest publishes. ``device_locator`` is in the EPUB's own container
    paths, so something has to point it back at the serving URL.
    """

    source: ResumeSource | None = None
    browser_locator: Mapping[str, Any] | None = None
    device_locator: Locator | None = None
    recorded_at: datetime | None = None

    @property
    def unresolved(self) -> bool:
        """Whether a position exists that could not be placed in this EPUB."""
        return (
            self.source is not None and self.browser_locator is None and self.device_locator is None
        )


NOWHERE = ResumePosition()
"""The answer for a book nobody has read anywhere: open at the beginning."""
