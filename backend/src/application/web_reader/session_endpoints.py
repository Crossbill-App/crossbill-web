"""A reading session's two endpoints: keyed for one derivation, rejoined after it.

The table holds a start and an end column, while the port converts a flat
mapping, so every caller deriving session Locators has to take the pair apart
and put it back together. The keying and the rejoining have to agree, so they
live together rather than once per ingest path.
"""

from collections.abc import Iterable, Mapping

from src.application.web_reader.anchors import Locator
from src.domain.common.value_objects.ids import ReadingSessionId
from src.domain.common.value_objects.xpoint import XPoint
from src.domain.reading.entities.reading_session import ReadingSession

type SessionEndpoint = tuple[ReadingSessionId, str]

_START = "start"
_END = "end"


def endpoint_xpoints(sessions: Iterable[ReadingSession]) -> dict[SessionEndpoint, XPoint]:
    """Both endpoints of every session that has them, keyed so one parse covers all.

    ``start_xpoint`` is the whole span: its ``.start`` is where the reader began
    and its ``.end`` where they stopped, even though the table has two columns.
    """
    points: dict[SessionEndpoint, XPoint] = {}
    for session in sessions:
        if not session.start_xpoint:
            continue
        points[(session.id, _START)] = session.start_xpoint.start
        points[(session.id, _END)] = session.start_xpoint.end
    return points


def paired_by_session(
    asked: Mapping[SessionEndpoint, XPoint],
    derived: Mapping[SessionEndpoint, Locator | None],
) -> dict[ReadingSessionId, tuple[Locator | None, Locator | None]]:
    """Rejoin derived endpoints into the ``(start, end)`` pair each row stores.

    Keyed off what was asked for rather than what came back, so a session whose
    endpoints both failed is still written and its row records the digest they
    failed against.
    """
    return {
        session_id: (derived.get((session_id, _START)), derived.get((session_id, _END)))
        for session_id in dict.fromkeys(session_id for session_id, _ in asked)
    }
