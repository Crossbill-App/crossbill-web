"""Tests for Position value object."""

from src.domain.common.value_objects.position import Position


class TestPosition:
    """Test suite for Position value object."""

    def test_ordering_index_takes_precedence(self) -> None:
        pos1 = Position(index=10, char_index=999)
        pos2 = Position(index=11, char_index=0)
        assert pos1 < pos2
