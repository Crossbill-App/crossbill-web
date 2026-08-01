"""Tests for Position value object."""

import pytest

from src.domain.common.value_objects.position import Position


class TestPosition:
    """Test suite for Position value object."""

    def test_create_with_defaults(self) -> None:
        pos = Position(index=42)
        assert pos.index == 42
        assert pos.char_index == 0

    def test_create_with_char_index(self) -> None:
        pos = Position(index=42, char_index=50)
        assert pos.index == 42
        assert pos.char_index == 50

    def test_is_frozen(self) -> None:
        pos = Position(index=1)
        with pytest.raises(AttributeError):
            pos.index = 2  # type: ignore[misc]

    def test_ordering_by_index(self) -> None:
        pos1 = Position(index=10)
        pos2 = Position(index=20)
        assert pos1 < pos2
        assert pos2 > pos1

    def test_ordering_by_char_index(self) -> None:
        pos1 = Position(index=10, char_index=5)
        pos2 = Position(index=10, char_index=50)
        assert pos1 < pos2

    def test_ordering_index_takes_precedence(self) -> None:
        pos1 = Position(index=10, char_index=999)
        pos2 = Position(index=11, char_index=0)
        assert pos1 < pos2

    def test_equality(self) -> None:
        pos1 = Position(index=42, char_index=10)
        pos2 = Position(index=42, char_index=10)
        assert pos1 == pos2

    def test_range_check(self) -> None:
        """Position works with <= for range containment checks."""
        start = Position(index=10, char_index=0)
        end = Position(index=20, char_index=100)
        inside = Position(index=15, char_index=50)
        before = Position(index=5, char_index=0)
        after = Position(index=25, char_index=0)

        assert start <= inside <= end
        assert not (start <= before)
        assert not (after <= end)

    def test_to_json(self) -> None:
        pos = Position(index=42, char_index=10)
        assert pos.to_json() == [42, 10]

    def test_from_json(self) -> None:
        pos = Position.from_json([42, 10])
        assert pos.index == 42
        assert pos.char_index == 10

    def test_from_json_roundtrip(self) -> None:
        original = Position(index=100, char_index=55)
        restored = Position.from_json(original.to_json())
        assert restored == original
