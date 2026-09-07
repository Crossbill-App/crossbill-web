"""How much a hostile declaration can make the position list allocate.

The endpoint tests assert what a request answers. This one asserts what building
the answer *costs*, which no status code can show and which is the whole point
of the bound: a position list is derived arithmetic rather than copied bytes, so
a few hundred bytes of archive can ask for gigabytes of response, and the
refusal has to happen before the list exists rather than after.
"""

import tracemalloc

import pytest

from src.application.web_reader.publications import PublicationLayout, PublicationResource
from src.domain.library.exceptions import InvalidEbookError
from src.infrastructure.web_reader.queries.publication_positions_query import (
    MAX_PUBLICATION_POSITIONS,
    POSITION_LENGTH,
    position_list,
)

CHAPTER = PublicationResource(href="c1.xhtml", media_type="application/xhtml+xml")


def peak_bytes_listing(
    reading_order: tuple[PublicationResource, ...], sizes: dict[str, int]
) -> tuple[object, int]:
    """Cut a reading order into positions and report what it peaked at, outcome and all."""
    tracemalloc.start()
    try:
        try:
            outcome: object = position_list(reading_order, sizes)
        except InvalidEbookError as e:
            outcome = e
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    return outcome, peak


def test_cuts_an_ordinary_reading_order_into_positions() -> None:
    """Should build the list when the declaration is one a real book could make."""
    positions, _ = peak_bytes_listing((CHAPTER,), {"c1.xhtml": 4 * POSITION_LENGTH})

    assert isinstance(positions, tuple)
    assert len(positions) == 4


def test_a_publication_declaring_millions_of_positions_is_never_materialised() -> None:
    """Should refuse on the arithmetic rather than allocate the list and then judge it.

    Two gigabytes of declared markup is two million positions. Counting them is
    a sum over a handful of integers; building them is hundreds of megabytes,
    and a check placed after the loop would pay that in full before refusing.
    """
    outcome, peak = peak_bytes_listing((CHAPTER,), {"c1.xhtml": 2 * 1024**3})

    assert isinstance(outcome, InvalidEbookError)
    assert peak < 1024 * 1024, f"built the list before refusing it ({peak} bytes)"


def test_the_ceiling_itself_is_still_served() -> None:
    """Should admit a publication sitting exactly on the limit, not one past it."""
    at_the_limit = MAX_PUBLICATION_POSITIONS * POSITION_LENGTH

    positions, _ = peak_bytes_listing((CHAPTER,), {"c1.xhtml": at_the_limit})

    assert isinstance(positions, tuple)
    assert len(positions) == MAX_PUBLICATION_POSITIONS

    with pytest.raises(InvalidEbookError, match="positions"):
        position_list((CHAPTER,), {"c1.xhtml": at_the_limit + 1})


def test_a_fixed_layout_declaration_costs_one_position_however_large() -> None:
    """Should not let a fixed-layout member's declared size buy positions at all.

    Its size never reaches the arithmetic, so the ceiling is not what protects
    it -- the layout is.
    """
    page = PublicationResource(
        href="p1.xhtml",
        media_type="application/xhtml+xml",
        layout=PublicationLayout.FIXED,
    )

    positions, peak = peak_bytes_listing((page,), {"p1.xhtml": 2 * 1024**3})

    assert isinstance(positions, tuple)
    assert len(positions) == 1
    assert peak < 1024 * 1024
