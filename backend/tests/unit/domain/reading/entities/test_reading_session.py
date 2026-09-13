"""What extending an ongoing session carries forward and what it refuses.

A session synced from an e-reader arrives complete; only a reader reporting its
position as it goes extends one, and no endpoint does that yet.
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.domain.common.exceptions import DomainError
from src.domain.common.value_objects import BookId, UserId, XPoint, XPointRange
from src.domain.common.value_objects.position import Position
from src.domain.reading.entities.reading_session import ReadingSession

STARTED = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
LATER = STARTED + timedelta(minutes=10)


def a_page(number: int) -> XPoint:
    return XPoint.parse(f"/body/DocFragment[{number}]/body/div[1]/p[1]")


def a_session(
    start_page: int | None = None,
    end_page: int | None = None,
    start_xpoint: XPointRange | None = None,
    end_position: Position | None = None,
) -> ReadingSession:
    return ReadingSession.create(
        user_id=UserId(1),
        book_id=BookId(2),
        start_time=STARTED,
        end_time=STARTED,
        start_page=start_page,
        end_page=end_page,
        start_xpoint=start_xpoint,
        end_position=end_position,
    )


class TestTheEndTime:
    def test_extending_moves_the_end_time_forward(self) -> None:
        session = a_session()

        session.extend_to(LATER)

        assert session.end_time == LATER

    def test_an_earlier_moment_leaves_the_end_time_but_still_takes_the_position(self) -> None:
        """A write that overtook another must not shorten a session that really ran that long."""
        session = a_session()
        session.extend_to(LATER, position=Position(index=9))

        session.extend_to(STARTED + timedelta(minutes=1), position=Position(index=3))

        assert session.end_time == LATER
        assert session.end_position == Position(index=3)

    def test_a_moment_before_the_session_started_is_refused(self) -> None:
        session = a_session()

        with pytest.raises(DomainError):
            session.extend_to(STARTED - timedelta(seconds=1))

    def test_the_moment_a_session_started_is_accepted(self) -> None:
        session = a_session()

        session.extend_to(STARTED, position=Position(index=3))

        assert session.end_position == Position(index=3)

    def test_a_naive_moment_is_read_as_utc_rather_than_refused(self) -> None:
        session = a_session()

        session.extend_to(LATER.replace(tzinfo=None))

        assert session.end_time == LATER


class TestWhereTheReaderIs:
    def test_the_end_position_follows_the_reader_backwards(self) -> None:
        """Reading progress is read from it, so it is where the reader is, not the furthest."""
        session = a_session(end_position=Position(index=40))

        session.extend_to(LATER, position=Position(index=12))

        assert session.end_position == Position(index=12)

    def test_extending_without_a_position_leaves_the_stored_one(self) -> None:
        session = a_session(end_position=Position(index=40))

        session.extend_to(LATER)

        assert session.end_position == Position(index=40)


class TestThePageRange:
    def test_the_end_page_keeps_the_furthest_reached(self) -> None:
        session = a_session(start_page=1, end_page=40)

        session.extend_to(LATER, page=12)

        assert session.end_page == 40

    def test_a_further_page_moves_the_end_page(self) -> None:
        session = a_session(start_page=1, end_page=40)

        session.extend_to(LATER, page=55)

        assert session.end_page == 55

    def test_the_start_page_is_learned_from_the_first_write_that_carries_one(self) -> None:
        session = a_session()

        session.extend_to(LATER, page=12)

        assert session.start_page == 12
        assert session.end_page == 12

    def test_a_later_write_does_not_move_the_start_page(self) -> None:
        session = a_session()
        session.extend_to(LATER, page=12)

        session.extend_to(LATER + timedelta(minutes=1), page=20)

        assert session.start_page == 12
        assert session.end_page == 20


class TestTheXpointRange:
    def test_the_range_grows_to_where_the_reader_now_is(self) -> None:
        session = a_session(start_xpoint=XPointRange(start=a_page(1), end=a_page(2)))

        session.extend_to(LATER, xpoint=a_page(9))

        assert session.start_xpoint == XPointRange(start=a_page(1), end=a_page(9))

    def test_a_reader_paging_back_past_where_the_sitting_opened_leaves_the_range(self) -> None:
        session = a_session(start_xpoint=XPointRange(start=a_page(4), end=a_page(9)))

        session.extend_to(LATER, xpoint=a_page(2))

        assert session.start_xpoint == XPointRange(start=a_page(4), end=a_page(9))

    def test_a_reader_paging_back_within_the_sitting_leaves_the_range(self) -> None:
        """The ordinary page-back, and the one a range built from the start would lose."""
        session = a_session(start_xpoint=XPointRange(start=a_page(1), end=a_page(9)))

        session.extend_to(LATER, xpoint=a_page(5))

        assert session.start_xpoint == XPointRange(start=a_page(1), end=a_page(9))

    def test_a_session_with_no_range_yet_gains_none(self) -> None:
        """There is no start to range from; the session's first write is what carries one."""
        session = a_session()

        session.extend_to(LATER, xpoint=a_page(9))

        assert session.start_xpoint is None
