"""Pydantic shapes for the locators a highlight derives to (M3.1, #745)."""

from pydantic import BaseModel, Field

from src.application.web_reader.queries.highlight_locators import (
    DerivedHighlightLocator,
    LocatorUnavailable,
)
from src.infrastructure.web_reader.schemas.locator_builders import served_locator_schema
from src.infrastructure.web_reader.schemas.reading_position_schemas import LocatorSchema


class HighlightLocator(BaseModel):
    """Where a highlight is in the EPUB, or why that cannot be said.

    Exactly one of the two fields is set, and a client must handle both: a
    locator here is derived from the stored xpointer at request time and
    verified against the highlight's own text, so a book whose EPUB has been
    replaced answers with reasons rather than with places (ADR-0004 §5).
    """

    locator: LocatorSchema | None = Field(
        None,
        description=(
            "The verified Readium locator, with hrefs in the same coordinates the "
            "manifest publishes. Null when the highlight cannot be placed."
        ),
    )
    unavailable: LocatorUnavailable | None = Field(
        None,
        description=(
            "Why there is no locator: 'no_ebook' (the book has no EPUB), "
            "'not_placeable' (the highlight was never given a position), "
            "'unresolved' (its position names nothing in this EPUB) or "
            "'text_mismatch' (it resolved, but onto different text -- the shape a "
            "replaced edition takes). Null when the locator is present."
        ),
    )


class HighlightLocatorResponse(HighlightLocator):
    """One highlight's locator, as the single-highlight endpoint answers it."""

    highlight_id: int = Field(..., description="The highlight this locator is for")


def build_highlight_locator(derived: DerivedHighlightLocator) -> HighlightLocator:
    """Render a derived locator in the coordinates a navigator speaks."""
    return HighlightLocator(
        locator=served_locator_schema(derived.locator) if derived.locator else None,
        unavailable=derived.unavailable,
    )
