"""How a reading order is cut into positions, and what a hostile one may cost."""

import tracemalloc

import pytest

from src.application.web_reader.publications import PublicationLayout, PublicationResource
from src.application.web_reader.queries.publication_positions import (
    MAX_PUBLICATION_POSITIONS,
    POSITION_LENGTH,
    PublicationPosition,
    position_list,
)
from src.domain.library.exceptions import InvalidEbookError

XHTML = "application/xhtml+xml"

# Enough positions for the per-position cost to be measurable over tracemalloc's
# own noise, and few enough to keep the measurement quick.
ADMITTED_POSITIONS = 20_000


def chapter(href: str, size: int, layout: PublicationLayout | None = None) -> PublicationResource:
    return PublicationResource(href=href, media_type=XHTML, size=size, layout=layout)


def peak_bytes_listing(
    reading_order: tuple[PublicationResource, ...],
) -> tuple[tuple[PublicationPosition, ...] | InvalidEbookError, int]:
    """Cut a reading order into positions and report what it peaked at, outcome and all."""
    tracemalloc.start()
    try:
        outcome: tuple[PublicationPosition, ...] | InvalidEbookError
        try:
            outcome = position_list(reading_order)
        except InvalidEbookError as e:
            outcome = e
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    return outcome, peak


def test_positions_run_on_across_resources_while_progression_restarts() -> None:
    positions = position_list((chapter("c1.xhtml", 2500), chapter("c2.xhtml", 1500)))

    assert [(p.href, p.position) for p in positions] == [
        ("c1.xhtml", 1),
        ("c1.xhtml", 2),
        ("c1.xhtml", 3),
        ("c2.xhtml", 4),
        ("c2.xhtml", 5),
    ]
    assert [p.progression for p in positions] == pytest.approx([0.0, 1 / 3, 2 / 3, 0.0, 0.5])
    assert [p.total_progression for p in positions] == pytest.approx([0.0, 0.2, 0.4, 0.6, 0.8])


def test_a_fixed_layout_resource_is_one_position_however_large() -> None:
    page = chapter("p1.xhtml", 2 * 1024**3, layout=PublicationLayout.FIXED)

    positions = position_list((page,))

    assert positions == (
        PublicationPosition(
            href="p1.xhtml", media_type=XHTML, position=1, progression=0.0, total_progression=0.0
        ),
    )


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


def test_an_oversized_declaration_is_refused_before_the_list_is_built() -> None:
    """Should refuse on the arithmetic rather than allocate the list and then judge it.

    Cheap on its own proves nothing, so the cost of an admitted list of known
    size sets the scale the refusal is measured against.
    """
    admitted, admitted_peak = peak_bytes_listing(
        (chapter("c1.xhtml", ADMITTED_POSITIONS * POSITION_LENGTH),)
    )
    assert isinstance(admitted, tuple)
    assert len(admitted) == ADMITTED_POSITIONS

    refused, refused_peak = peak_bytes_listing((chapter("c1.xhtml", 2 * 1024**3),))

    assert isinstance(refused, InvalidEbookError)
    assert refused_peak < admitted_peak, (
        f"refusing a hundredfold longer list peaked at {refused_peak} bytes, over the "
        f"{admitted_peak} that building {ADMITTED_POSITIONS} positions costs"
    )
