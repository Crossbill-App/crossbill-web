"""Reading timestamps back out of stores that do not all record a zone."""

from datetime import UTC, datetime


def as_aware(moment: datetime) -> datetime:
    """Read a zoneless timestamp as UTC -- every store we read from records UTC.

    SQLite has no timestamp type that keeps an offset, so a column declared
    ``DateTime(timezone=True)`` comes back naive there and aware on PostgreSQL.
    Two timestamps are only comparable once both have been read this way, and
    the alternative -- comparing whatever the driver happened to return -- is a
    ``TypeError`` on one dialect and not the other.
    """
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)
