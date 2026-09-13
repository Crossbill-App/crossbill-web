from datetime import UTC, timedelta

from src.infrastructure.reading.schemas.reading_session_schemas import ReadingSessionSyncItem


def _item(start_time: str, end_time: str) -> ReadingSessionSyncItem:
    return ReadingSessionSyncItem.model_validate(
        {
            "start_time": start_time,
            "end_time": end_time,
            "start_page": 10,
            "end_page": 25,
        }
    )


def test_naive_session_timestamp_is_localised_to_utc() -> None:
    item = _item("2024-01-15T10:00:00", "2024-01-15T11:00:00")

    assert item.start_time.tzinfo is UTC
    assert item.start_time.utcoffset() == timedelta(0)


def test_offset_session_timestamp_is_normalised_to_utc() -> None:
    item = _item("2024-01-15T10:00:00+02:00", "2024-01-15T11:00:00+02:00")

    assert item.start_time.isoformat() == "2024-01-15T08:00:00+00:00"
