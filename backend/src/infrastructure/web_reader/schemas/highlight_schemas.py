"""Pydantic shapes for a highlight the reader makes in the browser.

The request carries the same Readium Locator Object the reading-position write
takes, with the one field a selection cannot do without: ``text.highlight`` is the
selected text, so it is both what gets anchored in the book and what gets stored as
the highlight, and there is no second copy of it to disagree.
"""

from datetime import datetime as dt

from pydantic import BaseModel, Field, model_validator

from src.infrastructure.web_reader.schemas.reading_position_schemas import BrowserLocatorSchema


class SelectionHighlightCreate(BaseModel):
    """What the reader sends when they have highlighted a passage.

    Named for the selection rather than for the highlight because the KOReader
    sync's own upload item is already ``HighlightCreate``, and two schemas of
    that name would leave every generated client calling both by their full
    module paths.
    """

    locator: BrowserLocatorSchema = Field(
        ...,
        description=(
            "What the reader selected. Unlike the reading position's locator this one "
            "must quote its `text.highlight`: that is the selected text, and it is both "
            "what gets anchored in the book and what gets stored as the highlight."
        ),
    )

    note: str | None = Field(
        None,
        description=(
            "What the reader wrote about the passage. Stored as the highlight's "
            "device-side note, which is the one an e-reader shows and edits."
        ),
    )
    highlight_style_id: int | None = Field(
        None,
        description=(
            "The label to file this highlight under -- one of the book's own, as "
            "`GET /books/{book_id}/highlight-labels` lists them."
        ),
    )

    @model_validator(mode="after")
    def require_selected_text(self) -> "SelectionHighlightCreate":
        """Refuse a selection that quotes nothing, or nothing but whitespace.

        The one field a selection cannot do without, checked here rather than left
        to the use case so that a browser sending an empty range is answered by the
        same 422 as any other malformed body.
        """
        if not (self.locator.text.highlight or "").strip():
            raise ValueError("locator.text.highlight is required: a highlight needs its text")
        return self


class CreatedHighlightResponse(BaseModel):
    """The highlight that is now stored for the selected passage."""

    id: int = Field(description="The highlight, for drawing it and for editing it later")
    book_id: int
    chapter_id: int | None = Field(
        None, description="The chapter whose range holds it, if the book's chapters are placed"
    )
    text: str = Field(description="The selected text, as it is stored")
    note: str | None = None
    highlight_style_id: int | None = None
    start_xpoint: str | None = Field(
        None,
        description=(
            "Where the passage starts, in the format both readers agree on. Null only "
            "for a highlight stored before an e-reader sent its coordinates."
        ),
    )
    end_xpoint: str | None = Field(None, description="Where it ends, on the same terms")
    datetime: dt = Field(
        description=(
            "When the highlight was made, as a wall clock with no offset -- the same "
            "convention an e-reader's own timestamp arrives in."
        )
    )
