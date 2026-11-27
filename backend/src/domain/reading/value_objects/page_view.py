"""PageView value object."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from src.domain.common.exceptions import DomainError
from src.domain.common.value_objects import XPoint
from src.domain.common.value_objects.position import Position


@dataclass(frozen=True)
class PageView:
    """One appearance of a page on screen during a Reading Session.

    ``start_offset`` and ``end_offset`` count characters from the start of the
    book, and ``position_source_hash`` names the EPUB the positions and offsets
    were derived from.
    """

    start_xpoint: XPoint
    end_xpoint: XPoint
    start_position: Position
    end_position: Position
    start_offset: int
    end_offset: int
    position_source_hash: str
    shown_at: datetime
    duration: timedelta

    def __post_init__(self) -> None:
        if self.duration < timedelta(0):
            raise DomainError("A Page View cannot last less than no time")
        if self.end_offset < self.start_offset:
            raise DomainError("A Page View cannot end before it starts")
