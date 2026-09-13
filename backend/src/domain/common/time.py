"""Reading stored timestamps against each other."""

from datetime import UTC, datetime


def as_aware(moment: datetime) -> datetime:
    """Read a zoneless timestamp as UTC -- every store we read sessions from records UTC."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)
