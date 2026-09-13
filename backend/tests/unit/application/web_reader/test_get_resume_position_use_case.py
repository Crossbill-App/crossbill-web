"""Weighing a synced session against a browser position when only one says its zone.

Postgres hands back both stored moments with a zone and SQLite hands back neither,
so the API tier can only ever see a matched pair. A KOReader sync that recorded a
zoneless UTC moment beside a browser position that named its zone is the mixed pair
no API test can construct.
"""

from datetime import UTC, datetime, timedelta

from src.application.web_reader.anchors import Locator, LocatorLocations
from src.application.web_reader.queries.get_resume_position_use_case import (
    GetResumePositionUseCase,
)
from src.application.web_reader.queries.resume_position import (
    BrowserPosition,
    DevicePosition,
    ResumeCandidates,
    ResumeSource,
)
from src.domain.common.value_objects.ids import BookId, UserId

DIGEST = "sha256-the-book-we-hold"
NOON = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)


class StoredCandidates:
    """A stand-in for the query adapter, answering with the places it was given."""

    def __init__(self, candidates: ResumeCandidates) -> None:
        self.candidates = candidates

    async def resume_candidates(self, book_id: BookId, user_id: UserId) -> ResumeCandidates:
        return self.candidates


def candidates(device_ended_at: datetime, browser_recorded_at: datetime) -> ResumeCandidates:
    return ResumeCandidates(
        publication_hash=DIGEST,
        browser=BrowserPosition(
            locator={"href": "resources/OEBPS/chapter2.xhtml", "type": "application/xhtml+xml"},
            source_hash=DIGEST,
            recorded_at=browser_recorded_at,
        ),
        device=DevicePosition(
            locator=Locator(
                href="OEBPS/chapter1.xhtml",
                type="application/xhtml+xml",
                locations=LocatorLocations(progression=0.25),
            ),
            source_hash=DIGEST,
            ended_at=device_ended_at,
        ),
    )


async def answer(device_ended_at: datetime, browser_recorded_at: datetime) -> ResumeSource | None:
    use_case = GetResumePositionUseCase(
        StoredCandidates(candidates(device_ended_at, browser_recorded_at))
    )
    resume = await use_case.get_resume_position(BookId(1), UserId(1))
    return resume.source


async def test_a_zoneless_session_a_minute_later_still_beats_the_browser() -> None:
    later = (NOON + timedelta(minutes=1)).replace(tzinfo=None)

    assert await answer(device_ended_at=later, browser_recorded_at=NOON) == ResumeSource.KOREADER


async def test_a_zoneless_session_a_minute_earlier_still_loses_to_the_browser() -> None:
    earlier = (NOON - timedelta(minutes=1)).replace(tzinfo=None)

    assert await answer(device_ended_at=earlier, browser_recorded_at=NOON) == ResumeSource.WEB
