"""The reader's own timezone and today, as request dependencies.

Shared by every endpoint whose answer is counted in calendar days: which day a
session falls on, and which day a year-long window ends on, are the reader's to
decide, not the server's. One module so that both endpoints resolve them the
same way -- and so that a test pinning today overrides one dependency rather
than one per route.
"""

from datetime import UTC, date, datetime, tzinfo
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends, Query


def reader_timezone(
    tz: Annotated[
        str,
        Query(description="IANA timezone the reader's calendar days are counted in"),
    ] = "UTC",
) -> tzinfo:
    """Read the caller's timezone, falling back to UTC when this server cannot resolve it.

    An unknown zone name shifts a day boundary at worst -- it is not worth
    failing the page over, and the reader would have got UTC anyway. ``ZoneInfo``
    resolves a key against the filesystem, so a malformed one surfaces as an
    ``OSError`` as readily as a lookup failure.
    """
    try:
        return ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return UTC


def reader_today(zone: Annotated[tzinfo, Depends(reader_timezone)]) -> date:
    """The date it is right now where the reader is.

    The activity grid's window ends here, so it is resolved once at the edge
    and handed down; nothing below this line reads the clock.
    """
    return datetime.now(zone).date()
