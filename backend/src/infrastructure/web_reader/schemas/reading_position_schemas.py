"""Pydantic shapes for the reading position a browser stores and gets back.

An *input* locator, unlike the derived one ``locator_schemas`` serves: it arrives
from the navigator rather than being computed, so every field is optional and the
JSON keys are Readium's camelCase. The same document goes back out, which is why the
aliases have to work in both directions -- whatever the browser can be put back by is
what it must be handed.
"""

from datetime import datetime as dt
from math import isfinite

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from src.application.web_reader.queries.publication_positions import MAX_PUBLICATION_POSITIONS
from src.application.web_reader.queries.resume_position import ResumeSource
from src.infrastructure.common.schemas.position_schemas import PositionResponse


class BrowserLocatorTextSchema(BaseModel):
    """A Locator's ``text``: what is at the position, and what surrounds it."""

    before: str | None = None
    highlight: str | None = None
    after: str | None = None


class BrowserLocatorLocationsSchema(BaseModel):
    """A Locator's ``locations``: the same place said in several ways.

    Every field is optional, because a navigator fills in only what its current view
    can supply. The two numeric ones are bounded here rather than defended downstream,
    because both feed arithmetic: ``position`` indexes a list this API served, so past
    its ceiling it indexes no list that could exist and would credit a sitting with
    billions of pages; a progression is multiplied by a resource's length.
    """

    model_config = ConfigDict(populate_by_name=True)

    position: int | None = Field(
        default=None,
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
    total_progression: float | None = Field(
        default=None,
        validation_alias=AliasChoices("totalProgression", "total_progression"),
        serialization_alias="totalProgression",
        description="How far into the whole publication the position sits, 0..1",
    )
    fragments: list[str] | None = None
    css_selector: str | None = Field(
        default=None,
        validation_alias=AliasChoices("cssSelector", "css_selector"),
        serialization_alias="cssSelector",
        description="A querySelector-resolvable selector for the enclosing element",
    )

    @field_validator("progression", mode="before")
    @classmethod
    def drop_non_finite(cls, value: object) -> object:
        """Read ``NaN`` and ``Infinity`` as no progression at all.

        Degraded rather than refused because a refusal would not survive: FastAPI
        quotes the offending value back, and a body quoting ``NaN`` cannot be
        serialised as JSON, so the 422 becomes a 500 and the caller learns nothing.
        """
        return None if isinstance(value, float) and not isfinite(value) else value

    @field_validator("position", mode="before")
    @classmethod
    def drop_page_off_the_list(cls, value: object) -> object:
        """Read a page outside this publication's position list as no page at all.

        The page is what a sitting is *labelled* with, while the locator beside it is
        the reading; refusing the write over a miscounted label would cost the reading.
        """
        off_list = isinstance(value, int) and not 1 <= value <= MAX_PUBLICATION_POSITIONS
        return None if off_list else value


class BrowserLocatorSchema(BaseModel):
    """A Readium Locator Object as a navigator produces and consumes one."""

    model_config = ConfigDict(populate_by_name=True)

    href: str = Field(..., description="The resource, as the manifest names it")
    type: str = Field(..., description="The resource's media type")
    title: str | None = None
    locations: BrowserLocatorLocationsSchema = BrowserLocatorLocationsSchema()
    text: BrowserLocatorTextSchema = BrowserLocatorTextSchema()


class ReadingPositionUpdate(BaseModel):
    """What the reader sends when they have moved."""

    locator: BrowserLocatorSchema = Field(..., description="Where the reader now is")
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
            "Whether the reader is leaving the book. The position is stored either "
            "way; this ends the reading session rather than leaving it to be "
            "extended."
        ),
    )


class ReadingPosition(BaseModel):
    """Where a reader last was in a book, as the browser gets it back."""

    locator: BrowserLocatorSchema = Field(..., description="The position, ready to navigate to")
    xpoint: str = Field(..., description="The same position in the format both readers agree on")
    position: PositionResponse | None = Field(
        None,
        description="The position in document order, or null when it could not be placed",
    )
    updated_at: dt = Field(..., description="When this position was recorded")


class ResumePositionResponse(BaseModel):
    """Where the web reader should open a book, whichever device was there last.

    Read it as: navigate to ``locator`` if there is one; otherwise start at the
    beginning, and say so if ``unresolved``.
    """

    locator: BrowserLocatorSchema | None = Field(
        None,
        description=(
            "Where to open the book, in the coordinates the manifest publishes, "
            "or null when there is nowhere to resume to"
        ),
    )
    source: ResumeSource | None = Field(
        None,
        description=(
            "Which reader the position came from -- 'web' for this browser's own "
            "stored place, 'koreader' for the end of a session synced from an "
            "e-reader. Null when the book has been read nowhere."
        ),
    )
    unresolved: bool = Field(
        False,
        description=(
            "Whether a place was recorded that cannot be placed in the EPUB this "
            "server now holds -- typically the file has been replaced. The book "
            "opens at the beginning and the reader is told their place was lost."
        ),
    )
    recorded_at: dt | None = Field(
        None, description="When the reader was at this position, by their own device's clock"
    )
