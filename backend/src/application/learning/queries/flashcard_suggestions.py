"""Read model shared by the three flashcard-suggestion views.

The suggestion reads are ports of the ADR's halfway option: they still ask
repositories for aggregates and hand the text to the AI service, so there is no
query adapter here -- only the shape the routers render.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FlashcardSuggestion:
    """One question/answer pair the AI proposed for a highlight, chapter or note."""

    question: str
    answer: str
