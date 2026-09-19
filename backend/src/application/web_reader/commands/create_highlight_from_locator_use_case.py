"""Store a highlight a reader made by selecting text in the browser."""

import asyncio
from dataclasses import dataclass
from datetime import datetime

import structlog

from src.application.common.ownership import require_book
from src.application.library.protocols.book_repository import BookRepositoryProtocol
from src.application.library.protocols.chapter_repository import ChapterRepositoryProtocol
from src.application.library.protocols.file_repository import FileRepositoryProtocol
from src.application.library.protocols.position_index_service import PositionIndexServiceProtocol
from src.application.reading.protocols.highlight_repository import HighlightRepositoryProtocol
from src.application.reading.protocols.highlight_style_repository import (
    HighlightStyleRepositoryProtocol,
)
from src.application.semantic.content_type import ContentType
from src.application.semantic.protocols.embedding_enqueuer import EmbeddingEnqueuerProtocol
from src.application.web_reader.anchors import (
    AnchorConfidence,
    AnchorMatch,
    AnchorNotFoundError,
    AnchorResolutionError,
    AnchorSource,
    Locator,
)
from src.application.web_reader.protocols.position_anchor_service import (
    PositionAnchorServiceProtocol,
)
from src.application.web_reader.publications import epub_content_hash
from src.domain.common.devices import WEB_READER_DEVICE_ID
from src.domain.common.exceptions import ValidationError
from src.domain.common.value_objects import (
    BookId,
    ChapterId,
    ContentHash,
    HighlightStyleId,
    UserId,
    XPointRange,
)
from src.domain.common.value_objects.position import Position
from src.domain.library.exceptions import EbookFileNotFoundError
from src.domain.library.services.chapter_position_resolver import ChapterPositionResolver
from src.domain.reading.entities.highlight import Highlight
from src.domain.reading.entities.highlight_style import KOREADER_DEFAULT_DRAWER
from src.domain.reading.exceptions import HighlightStyleNotFoundError
from src.domain.web_reader.exceptions import BookFileUnreadableError, UnresolvablePositionError

logger = structlog.get_logger(__name__)

# The weakest match a selection may be stored from.
#
# A highlight is a quote or it is nothing. The reader selected text and the browser
# sent it as ``text.highlight``, so a match anchored on an element or a progression
# instead has placed something other than what they selected, whatever its grade.
#
# Among quotes the floor is the weakest grade that still names *one* place: the quote
# occurs exactly once in its resource. ``AMBIGUOUS`` means it occurs several times and
# neither context settled which, and ``FUZZY`` means it is not in the resource as
# written; either would anchor the highlight over words the reader never selected,
# which is the failure ADR-0004 §5 exists to prevent. A selection made against this
# same EPUB moments earlier normally comes back well above the floor -- with both its
# contexts, or one where it abuts the edge of a resource.
MINIMUM_CONFIDENCE = AnchorConfidence.HIGHLIGHT_ONLY


@dataclass(frozen=True)
class CreatedHighlight:
    """A stored highlight, and whether this call is what stored it.

    ``created`` is false when the book already held the selected text: the same
    passage marked twice is one highlight, so the stored one is the answer.
    """

    highlight: Highlight
    created: bool


class CreateHighlightFromLocatorUseCase:
    """Turn a browser selection into a highlight both readers can see.

    The locator the navigator produced is resolved back to the canonical KOReader
    xpointers (ADR-0004 §2) and graded against :data:`MINIMUM_CONFIDENCE`, so a
    selection that cannot be placed in the book is refused rather than stored
    somewhere approximate. What is stored is an ordinary highlight -- the same row
    the KOReader sync writes, wearing the web reader's device id -- which is what
    lets it reach the e-reader through the pull that already exists.

    The locator itself is kept beside the xpointers, with the grade it resolved at.
    It is the *input* here rather than something derived (Amendment 6), so nothing
    is derived back from the xpointers it produced.
    """

    def __init__(
        self,
        book_repository: BookRepositoryProtocol,
        highlight_repository: HighlightRepositoryProtocol,
        chapter_repository: ChapterRepositoryProtocol,
        highlight_style_repository: HighlightStyleRepositoryProtocol,
        position_anchor_service: PositionAnchorServiceProtocol,
        file_repository: FileRepositoryProtocol,
        position_index_service: PositionIndexServiceProtocol,
        chapter_position_resolver: ChapterPositionResolver,
        embedding_enqueuer: EmbeddingEnqueuerProtocol,
    ) -> None:
        self.book_repository = book_repository
        self.highlight_repository = highlight_repository
        self.chapter_repository = chapter_repository
        self.highlight_style_repository = highlight_style_repository
        self.position_anchor_service = position_anchor_service
        self.file_repository = file_repository
        self.position_index_service = position_index_service
        self.chapter_position_resolver = chapter_position_resolver
        self.embedding_enqueuer = embedding_enqueuer

    async def create_highlight(
        self,
        book_id: int,
        user_id: int,
        locator: Locator,
        device_datetime: datetime,
        note: str | None = None,
        highlight_style_id: int | None = None,
        device_color: str | None = None,
        device_style: str | None = None,
    ) -> CreatedHighlight:
        """Store what the reader selected, or hand back the highlight already there.

        The passage is looked up by its text before the EPUB is read, so marking one
        the book already holds costs two queries rather than a parse -- and answers
        with the stored highlight whatever this selection would have resolved to. A
        note or label sent with such a selection is checked and then dropped: this
        creates a highlight, and changing one that exists is an edit (M4.4). A colour
        is dropped too, without creating the style it would have filed under.

        Args:
            book_id: The book being read.
            user_id: Whose highlight this is.
            locator: The selection, with hrefs already read back into the paths the
                publication uses internally. Its ``text.highlight`` is the selected
                text and becomes the highlight's own.
            device_datetime: When the reader made it, as a wall clock on their own
                clock with no offset -- what an e-reader sends.
            note: What the reader wrote about the passage, if anything. Stored as the
                highlight's device-side note, which is the one an e-reader shows.
            highlight_style_id: The label to file the highlight under -- one of the
                book's own, as ``GET /books/{id}/highlight-labels`` lists them.
            device_color: A KOReader colour name to file the highlight under instead,
                as the e-reader's own highlights are filed: the book's style for this
                colour and drawer, created if the book has none yet.
            device_style: The drawer that colour is drawn with, KOReader's own default
                when a colour arrives without one.

        Raises:
            BookNotFoundError: If the user has no such book.
            ValidationError: If the locator quotes no text, so there is nothing to
                highlight.
            HighlightStyleNotFoundError: If the label is not one of this book's.
            EbookFileNotFoundError: If the book has no EPUB to place a selection in.
            UnresolvablePositionError: If the EPUB does not hold the selected text, or
                holds it in too many places to say which was meant.
            BookFileUnreadableError: If the stored EPUB cannot be read at all.
        """
        user = UserId(user_id)
        book_id_vo = BookId(book_id)
        book = await require_book(self.book_repository, book_id_vo, user)

        text = (locator.text.highlight or "").strip()
        if not text:
            raise ValidationError(
                "A highlight needs the text it was made from", field="locator.text.highlight"
            )

        style = await self._label(highlight_style_id, book_id_vo, user)
        stored = await self.highlight_repository.find_by_content_hash(
            user, book_id_vo, ContentHash.compute(text)
        )
        if stored is not None:
            return CreatedHighlight(await self._revived(stored), created=False)

        epub_content = await self.file_repository.get_epub(book.ebook_file)
        if not epub_content:
            raise EbookFileNotFoundError(book_id)

        match = self._graded(await self._resolved(epub_content, locator), locator, book_id_vo)
        position = await self._position(epub_content, match.xpoints)

        # Only once the selection is placed: a refused one would otherwise leave a
        # style no highlight points at, listed among the book's labels.
        if device_color is not None:
            style = (
                await self.highlight_style_repository.find_or_create(
                    user, book_id_vo, device_color, device_style or KOREADER_DEFAULT_DRAWER
                )
            ).id

        highlight = Highlight.create(
            user_id=user,
            book_id=book_id_vo,
            text=text,
            chapter_id=await self._chapter(book_id_vo, user, position),
            xpoints=match.xpoints,
            position=position,
            highlight_style_id=style,
            device_datetime=device_datetime,
            koreader_note=note or None,
            origin_device_id=WEB_READER_DEVICE_ID,
        )
        saved = await self.highlight_repository.save(highlight)
        await self.highlight_repository.record_locator(
            saved.id, locator, match.confidence, epub_content_hash(epub_content)
        )
        await self.embedding_enqueuer.enqueue_for(ContentType.HIGHLIGHT, saved.id.value, user_id)

        logger.info(
            "web_highlight_created",
            book_id=book_id,
            highlight_id=saved.id.value,
            chapter_id=saved.chapter_id.value if saved.chapter_id else None,
            confidence=match.confidence.name,
        )
        return CreatedHighlight(saved, created=True)

    async def _resolved(self, epub_content: bytes, locator: Locator) -> AnchorMatch:
        """Convert the selection to the coordinates both readers share."""
        try:
            return await self.position_anchor_service.xpoint_range_for_locator(
                epub_content, locator
            )
        # The subclass first: one place the book does not hold is the writer's
        # problem, where an archive that cannot be read is the book's.
        except AnchorNotFoundError as exc:
            raise UnresolvablePositionError(str(exc)) from exc
        except AnchorResolutionError as exc:
            raise BookFileUnreadableError(str(exc)) from exc

    @staticmethod
    def _graded(match: AnchorMatch, locator: Locator, book_id: BookId) -> AnchorMatch:
        """Refuse a match too weak to be the passage the reader selected."""
        if match.anchored_by is not AnchorSource.QUOTE or match.confidence < MINIMUM_CONFIDENCE:
            logger.info(
                "rejected_weak_selection",
                book_id=book_id.value,
                href=locator.href,
                anchored_by=match.anchored_by.value,
                confidence=match.confidence.name,
            )
            raise UnresolvablePositionError(
                f"the selected text matched too weakly ({match.confidence.name})"
            )
        return match

    async def _position(self, epub_content: bytes, xpoints: XPointRange) -> Position | None:
        """Place the selection in document order, so every reading view can order it."""
        # Off the event loop: an index is lxml over every document of the book.
        index = await asyncio.to_thread(
            self.position_index_service.build_position_index, epub_content
        )
        return index.resolve(xpoints.start.to_string())

    async def _chapter(
        self, book_id: BookId, user: UserId, position: Position | None
    ) -> ChapterId | None:
        """Attribute the selection to the chapter whose range holds it.

        By position rather than by chapter number: the e-reader sends a number with
        every highlight it syncs and a browser selection carries none. A book whose
        chapters have no positions -- one uploaded before they were derived -- gets
        no attribution, exactly as the sync gets none when it cannot find the chapter
        a device named.
        """
        if position is None:
            return None
        chapters = await self.chapter_repository.find_all_by_book(book_id, user)
        chapter = self.chapter_position_resolver.chapter_at(chapters, position)
        return chapter.id if chapter else None

    async def _label(
        self, highlight_style_id: int | None, book_id: BookId, user: UserId
    ) -> HighlightStyleId | None:
        """Check that the label the reader picked is one of this book's.

        A style belonging to another book, or to another reader, is treated as
        missing: from here the two are indistinguishable.
        """
        if highlight_style_id is None:
            return None
        style = await self.highlight_style_repository.find_by_id(
            HighlightStyleId(highlight_style_id), user_id=user
        )
        if style is None or style.book_id != book_id:
            raise HighlightStyleNotFoundError(highlight_style_id)
        return style.id

    async def _revived(self, stored: Highlight) -> Highlight:
        """Bring back a stored highlight the reader had deleted, and hand it back.

        Selecting a passage again is as deliberate as the KOReader push that flags a
        highlight new on its device, and gets the same answer: the stored row comes
        back, with the flashcards, bookmarks and tags that still hang off it, rather
        than a second row appearing beside it -- which the unique constraint over the
        content hash would refuse anyway. What a web delete cascaded away is gone for
        good, so the embedding deleted with it is enqueued again here.

        The stored row's own coordinates are left alone. They are where the passage
        was found before, and this selection is no evidence that they are wrong; a row
        stored without any is the sync's gap to fill.
        """
        if not (stored.is_deleted() or stored.is_removed_from_devices()):
            return stored

        was_deleted = stored.is_deleted()
        if was_deleted:
            stored.restore()
        if stored.is_removed_from_devices():
            stored.restore_to_devices()
        revived = await self.highlight_repository.save(stored)
        if was_deleted:
            await self.embedding_enqueuer.enqueue_for(
                ContentType.HIGHLIGHT, revived.id.value, revived.user_id.value
            )

        logger.info(
            "web_highlight_revived",
            book_id=revived.book_id.value,
            highlight_id=revived.id.value,
            undeleted=was_deleted,
        )
        return revived
