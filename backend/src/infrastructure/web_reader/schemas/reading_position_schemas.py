"""Pydantic shapes for the reading position a browser stores and resumes from.

The locator here is an *input* shape, unlike the one a position list is built
from: it arrives from the navigator rather than being computed, so every field
is optional and the JSON keys are Readium's camelCase ones. What comes back out
is the same document, which is why the aliases work in both directions --
whatever the browser can be put back by is what it must be handed.
"""

from datetime import datetime as dt
from math import isfinite

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from src.application.web_reader.queries.publication_positions import MAX_PUBLICATION_POSITIONS
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

    The two numeric fields are bounded here rather than defended downstream,
    because both feed arithmetic. ``position`` is only ever a number the browser
    read out of a position list *this API served it*, so the ceiling is the most
    positions any publication may be cut into -- past that it indexes no list
    that could exist, and unbounded it was both a 500 (a value past the
    column's range) and a session credited with billions of pages. And a
    progression is multiplied by a resource's length and rounded, so ``NaN`` and
    ``Infinity`` -- which JSON has no literal for but Python's parser reads
    anyway -- have to be refused before they are arithmetic.
    """

    model_config = ConfigDict(populate_by_name=True)

    position: int | None = Field(
        default=None,
        ge=1,
        le=MAX_PUBLICATION_POSITIONS,
        description=(
            "1-based index into this publication's position list -- the synthetic "
            "page the reader is shown"
        ),
    )
    progression: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="How far into this resource the position sits, 0..1",
    )

    @field_validator("progression", mode="before")
    @classmethod
    def drop_non_finite(cls, value: object) -> object:
        """Read ``NaN`` and ``Infinity`` as no progression at all.

        Dropped rather than refused, and this is the one place in these schemas
        that degrades instead of validating. A rejection would be reported by
        FastAPI in a body that quotes the offending value back -- and a body
        quoting ``NaN`` cannot be serialised as JSON, so the 422 turns into a
        500 and the caller learns nothing at all. Read as absent, the locator
        goes on to be judged on what it does carry, and a locator carrying
        nothing else is refused with a message that says so.
        """
        return None if isinstance(value, float) and not isfinite(value) else value

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
