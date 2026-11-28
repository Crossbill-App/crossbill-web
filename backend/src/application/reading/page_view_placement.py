"""Placing a Page View in a book, shared by every reader that reports them."""

from datetime import datetime, timedelta

from src.domain.common.exceptions import DomainError
from src.domain.common.value_objects import XPoint
from src.domain.common.value_objects.position_index import PositionIndex
from src.domain.reading.value_objects.page_view import PageView


def place_page_view(
    position_index: PositionIndex,
    start_xpoint: str,
    end_xpoint: str,
    source_hash: str,
    shown_at: datetime,
    duration: timedelta,
) -> PageView | None:
    """Place a Page View by its xpoints, or ``None`` if they do not resolve or it is malformed."""
    start_position = position_index.resolve(start_xpoint)
    end_position = position_index.resolve(end_xpoint)
    start_offset = position_index.character_offset(start_xpoint)
    end_offset = position_index.character_offset(end_xpoint)
    if start_position is None or end_position is None or start_offset is None or end_offset is None:
        return None
    try:
        return PageView(
            start_xpoint=XPoint.parse(start_xpoint),
            end_xpoint=XPoint.parse(end_xpoint),
            start_position=start_position,
            end_position=end_position,
            start_offset=start_offset,
            end_offset=end_offset,
            position_source_hash=source_hash,
            shown_at=shown_at,
            duration=duration,
        )
    except DomainError:
        return None
