"""Pydantic schemas for the embeddings API responses: backfill, related and search."""

from datetime import datetime as dt

from pydantic import BaseModel, ConfigDict

from src.infrastructure.jobs.schemas.job_batch_schemas import JobBatchResponse


class BackfillResponse(BaseModel):
    """What a backfill request did.

    ``total_jobs`` is the field to key on, because it is the only one present in
    both outcomes: it is 0 exactly when nothing needed embedding, and then
    ``batch`` is null because no batch was created and there is nothing to poll.
    """

    total_jobs: int
    batch: JobBatchResponse | None


#: The grouped-search schemas are validated straight off the read model's view
#: dataclasses (``application/semantic/queries/content_search.py``) rather than
#: copied field by field, so each field name here must match the view's. A
#: mismatch is a ValidationError on the first request, which the API tests
#: assert every field of.
_FROM_VIEW = ConfigDict(from_attributes=True)


class SearchBookRef(BaseModel):
    """A book a search result belongs to."""

    model_config = _FROM_VIEW

    id: int
    title: str
    cover_file: str | None
    cover_blurhash: str | None


class BookSearchItem(BaseModel):
    """A book matched by its own title or author, so it carries no score."""

    model_config = _FROM_VIEW

    id: int
    title: str
    author: str | None
    cover_file: str | None
    cover_blurhash: str | None


class HighlightSearchItem(BaseModel):
    """A matched highlight, shaped for a highlight list row.

    ``id`` opens the highlight view at
    ``/book/{book_id}/highlights?highlightId={id}``.
    """

    model_config = _FROM_VIEW

    score: float
    id: int
    book_id: int
    book_title: str
    chapter_id: int | None
    chapter_name: str | None
    chapter_number: int | None
    text: str
    page: int | None
    datetime: dt
    cover_file: str | None
    cover_blurhash: str | None


class NoteSearchItem(BaseModel):
    """A matched note. ``books`` may be empty; a note need not link to any."""

    model_config = _FROM_VIEW

    score: float
    id: int
    books: list[SearchBookRef]
    title: str
    body: str
    kind: str | None


class DigestSearchItem(BaseModel):
    """A matched chapter digest.

    ``id`` is the digest -- the unit that was embedded, and what ``score``
    belongs to. ``chapter_id`` is what ``/book/{book_id}/structure?chapterId=``
    opens.
    """

    model_config = _FROM_VIEW

    score: float
    id: int
    book_id: int
    book_title: str
    chapter_id: int
    chapter_name: str
    chapter_number: int | None
    summary: str
    keypoints: list[str]
    cover_file: str | None
    cover_blurhash: str | None


class RankedContentGroups(BaseModel):
    """Matches ranked against the embeddings index, grouped by content type.

    Every group is present even when empty, and every item carries its score on
    one scale, so a client can merge the groups back into a single ranked list.

    The whole of what ``GET /semantic/related`` answers, and the ranked half of
    global search.
    """

    model_config = _FROM_VIEW

    highlights: list[HighlightSearchItem]
    notes: list[NoteSearchItem]
    digests: list[DigestSearchItem]


class GlobalSearchResults(RankedContentGroups):
    """What ``GET /search`` answers: the ranked groups plus books matched by name.

    ``books`` is unranked and carries no score: a title or author match is not a
    similarity, so it cannot be merged into the ranking -- a client that wants
    one list puts the books above it.
    """

    books: list[BookSearchItem]
