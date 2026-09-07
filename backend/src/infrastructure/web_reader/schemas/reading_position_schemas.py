"""Pydantic shapes for the reading position a browser stores and resumes from.

The locator here is an *input* shape, unlike the one a position list is built
from: it arrives from the navigator rather than being computed, so every field
is optional and the JSON keys are Readium's camelCase ones. What comes back out
is the same document, which is why the aliases work in both directions --
whatever the browser can be put back by is what it must be handed.
"""

from datetime import datetime as dt

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from src.infrastructure.common.schemas.position_schemas import PositionResponse


class LocatorTextSchema(BaseModel):
    """A Locator's text quote: what is at the position, and what surrounds it.

    For a reading position ``highlight`` is the text the page begins on rather
    than anything the reader marked; ``before`` and ``after`` are what make it
    findable when the same sentence occurs twice.
    """

    before: str | None = None
    highlight: str | None = None
    after: str | None = None


class LocatorLocationsSchema(BaseModel):
    """A Locator's ``locations``: the same place said in several ways.

    Every field is optional because a navigator fills in only what its current
    view can supply, and all of them are kept: the resume that M2.4 builds on
    tries the text quote, then the CSS selector, then a fragment id, then the
    progression, in that order.
    """

    model_config = ConfigDict(populate_by_name=True)

    position: int | None = None
    progression: float | None = None
    total_progression: float | None = Field(
        default=None,
        validation_alias=AliasChoices("totalProgression", "total_progression"),
        serialization_alias="totalProgression",
    )
    fragments: list[str] | None = None
    css_selector: str | None = Field(
        default=None,
        validation_alias=AliasChoices("cssSelector", "css_selector"),
        serialization_alias="cssSelector",
    )


class LocatorSchema(BaseModel):
    """A Readium Locator Object as a navigator produces and consumes one."""

    model_config = ConfigDict(populate_by_name=True)

    href: str = Field(..., description="The resource, as the manifest names it")
    type: str = Field(..., description="The resource's media type")
    title: str | None = None
    locations: LocatorLocationsSchema = LocatorLocationsSchema()
    text: LocatorTextSchema = LocatorTextSchema()


class ReadingPositionUpdate(BaseModel):
    """What the reader sends when they have moved."""

    locator: LocatorSchema = Field(..., description="Where the reader now is")
    recorded_at: dt = Field(
        ...,
        description=(
            "When the reader was there, by their own clock. Never read as later "
            "than the moment the request arrives."
        ),
    )
    closing: bool = Field(
        False,
        description=(
            "Whether the reader is leaving the book. The position is stored "
            "either way; this ends the reading session rather than extending it "
            "next time."
        ),
    )


class ReadingPosition(BaseModel):
    """Where a reader last was in a book, as the browser gets it back."""

    locator: LocatorSchema = Field(..., description="The position, ready to navigate to")
    xpoint: str = Field(..., description="The same position in the format both readers agree on")
    position: PositionResponse | None = Field(
        None,
        description="The position in document order, or null when it could not be placed",
    )
    updated_at: dt = Field(..., description="When this position was recorded")
