"""Unit tests for the Highlight aggregate's device-removal state.

Removal from devices is a second, non-destructive lifecycle alongside soft
deletion: the highlight stays on the web and only disappears from e-readers.
No endpoint sets it yet, so these guards are unreachable from the API tier.
"""

import pytest

from src.domain.common.exceptions import DomainError
from src.domain.common.value_objects.ids import BookId, UserId
from src.domain.reading.entities.highlight import Highlight


def _create() -> Highlight:
    return Highlight.create(
        user_id=UserId(1),
        book_id=BookId(2),
        text="A passage worth keeping on the web.",
    )


def test_new_highlight_is_not_removed_from_devices() -> None:
    highlight = _create()

    assert highlight.is_removed_from_devices() is False
    assert highlight.removed_from_devices_at is None


def test_remove_from_devices_stamps_the_timestamp() -> None:
    highlight = _create()

    highlight.remove_from_devices()

    assert highlight.is_removed_from_devices() is True
    assert highlight.removed_from_devices_at is not None


def test_remove_from_devices_does_not_soft_delete() -> None:
    highlight = _create()

    highlight.remove_from_devices()

    assert highlight.is_deleted() is False
    assert highlight.deleted_at is None


def test_removing_twice_raises() -> None:
    highlight = _create()
    highlight.remove_from_devices()

    with pytest.raises(DomainError):
        highlight.remove_from_devices()


def test_restore_to_devices_clears_the_timestamp() -> None:
    highlight = _create()
    highlight.remove_from_devices()

    highlight.restore_to_devices()

    assert highlight.is_removed_from_devices() is False
    assert highlight.removed_from_devices_at is None


def test_restoring_a_highlight_that_is_on_devices_raises() -> None:
    highlight = _create()

    with pytest.raises(DomainError):
        highlight.restore_to_devices()


def test_soft_delete_leaves_the_device_state_alone() -> None:
    highlight = _create()

    highlight.soft_delete()

    assert highlight.is_deleted() is True
    assert highlight.is_removed_from_devices() is False
