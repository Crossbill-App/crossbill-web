"""Reading timestamps back out of stores that do not all record a zone."""

from datetime import UTC, datetime


def as_aware(moment: datetime) -> datetime:
    """Read a zoneless timestamp as UTC -- every store we read from records UTC.

    SQLite has no timestamp type that keeps an offset, so a column declared
    ``DateTime(timezone=True)`` comes back naive there and aware on PostgreSQL.
    Two timestamps are only comparable once both have been read this way, and
    the alternative -- comparing whatever the driver happened to return -- is a
    ``TypeError`` on one dialect and not the other.

    **This is a rule about storage, not about the wire, and it must stay one.**
    Every naive value it repairs is one a *store* dropped the offset from, and
    the offset it puts back is right because what went in was UTC. That holds
    only while nothing accepts a naive timestamp from a client and lets it reach
    a column: a device in Helsinki whose 20:00 were read here as 20:00 UTC would
    be placed three hours into its own future, and would win comparisons it
    should lose -- which is exactly what the web reader's resume does with a
    reading session's ``end_time`` (ADR-0004, Amendment 4). So the boundaries
    are where the offset is insisted upon: ``ReadingSessionSyncItem`` refuses a
    session moment without one, and highlights, whose device genuinely sends
    none, are stored in a column that keeps no offset either rather than being
    stamped with a guess.
    """
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)
