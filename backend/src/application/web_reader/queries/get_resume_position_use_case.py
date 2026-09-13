"""Read use case behind the reading-position read: where does this book open?"""

from src.application.web_reader.queries.resume_position import (
    NOWHERE,
    BrowserPosition,
    DevicePosition,
    ResumePosition,
    ResumePositionQueryProtocol,
    ResumeSource,
)
from src.domain.common.time import as_aware
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.reading.exceptions import BookNotFoundError


class GetResumePositionUseCase:
    """Answer where the web reader should open a book, across every device."""

    def __init__(self, resume_position_query: ResumePositionQueryProtocol) -> None:
        self.resume_position_query = resume_position_query

    async def get_resume_position(self, book_id: BookId, user_id: UserId) -> ResumePosition:
        """Return where to open this book, or :data:`NOWHERE` if it has been read nowhere.

        Raises:
            BookNotFoundError: If the user has no such book.
        """
        candidates = await self.resume_position_query.resume_candidates(book_id, user_id)
        if candidates is None:
            raise BookNotFoundError(book_id.value)
        browser, device = candidates.browser, candidates.device
        # Both moments are a reader's own clock saying when they were at a place,
        # which is the only comparison available: a KOReader session arrives here
        # whenever the device next syncs. A tie goes to the browser, whose locator
        # is what a navigator itself produced.
        if device is not None and (
            browser is None or as_aware(device.ended_at) > as_aware(browser.recorded_at)
        ):
            return _from_device(device, candidates.publication_hash)
        if browser is None:
            return NOWHERE
        return _from_browser(browser, candidates.publication_hash)


# Neither helper serves a locator whose source digest is no longer the book's -- it
# names a file the book no longer holds, and would place the reader in the wrong edition.
def _from_browser(browser: BrowserPosition, publication_hash: str | None) -> ResumePosition:
    placed = browser.source_hash == publication_hash
    return ResumePosition(
        source=ResumeSource.WEB,
        browser_locator=browser.locator if placed else None,
        recorded_at=as_aware(browser.recorded_at),
    )


def _from_device(device: DevicePosition, publication_hash: str | None) -> ResumePosition:
    placed = device.source_hash == publication_hash
    return ResumePosition(
        source=ResumeSource.KOREADER,
        device_locator=device.locator if placed else None,
        recorded_at=as_aware(device.ended_at),
    )
