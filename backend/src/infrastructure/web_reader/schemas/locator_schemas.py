"""Pydantic shapes for a derived Readium Locator, as a read model serves one.

Deliberately not the ``ReadiumLocator`` of ``readium_schemas``: a position list
always carries a position, a progression and a total progression, so those three
are required there, and relaxing them to serve both families would weaken the
TypeScript the reader already consumes. The apparent duplication is the cost of
keeping the position list's contract exact.
"""

from pydantic import BaseModel, Field

from src.application.web_reader.queries.highlight_locators import LocatorUnavailable


class LocatorTextSchema(BaseModel):
    """A Locator's ``text``: the anchored text and what surrounds it."""

    before: str | None = None
    highlight: str | None = None
    after: str | None = None


class LocatorLocationsSchema(BaseModel):
    """A Locator's ``locations``: the ways a derivation can express the position."""

    progression: float | None = None
    css_selector: str | None = Field(default=None, serialization_alias="cssSelector")


class LocatorSchema(BaseModel):
    """A Readium Locator naming one place in a publication."""

    href: str
    type: str
    locations: LocatorLocationsSchema
    text: LocatorTextSchema


class HighlightLocatorResponse(BaseModel):
    """Where one highlight is in the book's EPUB, or why that cannot be said."""

    highlight_id: int = Field(description="The highlight this answers for")
    locator: LocatorSchema | None = Field(
        default=None,
        description=(
            "The stored Readium locator, with hrefs in the same coordinates the "
            "manifest publishes. Absent whenever `unavailable` is present."
        ),
    )
    unavailable: LocatorUnavailable | None = Field(
        default=None,
        description="Why there is no locator. Absent whenever `locator` is present.",
    )
