"""The reader's own timezone and today, as request dependencies.

One module so that every endpoint counted in calendar days resolves them the
same way, and so a test pinning today overrides one dependency rather than one
per route.
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

    An unknown zone shifts a day boundary at worst, which is not worth failing
    the page over. ``ZoneInfo`` resolves against the filesystem, so a malformed
    key raises ``OSError`` as readily as a lookup failure.
    """
    try:
        return ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return UTC


def reader_today(zone: Annotated[tzinfo, Depends(reader_timezone)]) -> date:
    """The date it is right now where the reader is.

    Resolved once at the edge and handed down; nothing below reads the clock.
    """
    return datetime.now(zone).date()
