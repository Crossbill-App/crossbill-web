"""How a reading order is cut into positions."""

import pytest

from src.application.web_reader.publications import PublicationLayout, PublicationResource
from src.application.web_reader.queries.publication_positions import (
    MAX_PUBLICATION_POSITIONS,
    POSITION_LENGTH,
    position_list,
)
from src.domain.library.exceptions import InvalidEbookError

XHTML = "application/xhtml+xml"


def chapter(href: str, size: int, layout: PublicationLayout | None = None) -> PublicationResource:
    return PublicationResource(href=href, media_type=XHTML, size=size, layout=layout)


def test_a_resource_shorter_than_one_position_still_gets_one() -> None:
    positions = position_list((chapter("c1.xhtml", 0),))

    assert [(p.position, p.progression, p.total_progression) for p in positions] == [(1, 0.0, 0.0)]


def test_the_ceiling_is_served_and_one_byte_more_is_refused() -> None:
    at_the_limit = MAX_PUBLICATION_POSITIONS * POSITION_LENGTH

    positions = position_list((chapter("c1.xhtml", at_the_limit),))

    assert len(positions) == MAX_PUBLICATION_POSITIONS
    assert positions[-1].position == MAX_PUBLICATION_POSITIONS

    with pytest.raises(InvalidEbookError, match="positions"):
        position_list((chapter("c1.xhtml", at_the_limit + 1),))
