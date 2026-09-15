"""Which chapter of a book a document position falls in.

A pure domain service: the chapters and the position are entities and value
objects, and the answer is a rule rather than a query. It exists because the web
reader has to attribute a highlight made in the browser to a chapter and has no
chapter number to attribute it by -- the e-reader sends one with every highlight
it syncs, and a browser selection carries nothing but a place in the book.
"""

from collections.abc import Iterable
from sys import maxsize

from src.domain.common.value_objects.position import Position
from src.domain.library.entities.chapter import Chapter

# The end of a chapter that has none: the last entry of a table of contents runs
# to the end of the book, and sorts after every real end.
_ENDLESS = Position(index=maxsize, char_index=maxsize)


class ChapterPositionResolver:
    """Places a document position among a book's chapter ranges."""

    def chapter_at(self, chapters: Iterable[Chapter], position: Position) -> Chapter | None:
        """The chapter whose range holds ``position``, or ``None`` if none does.

        A chapter's range runs from ``start_position`` inclusive to
        ``end_position`` exclusive, because ``end_position`` *is* the next
        table-of-contents entry's start (``EpubParserService.parse_toc``). The
        ranges therefore partition the book in reading order rather than
        nesting, and the deepest entry wins without being asked to: a part whose
        first chapter starts where the part does ends there too, so the part is
        out and the chapter is in. The last entry has no end and runs to the end
        of the book.

        Where ranges do overlap -- a table of contents whose entries are not in
        reading order, or chapters positioned against an EPUB that has since
        been replaced -- the latest range holding the position wins, and among
        ranges that start together the tightest one does. That is the innermost
        chapter when the overlap is nesting.

        A chapter with no ``start_position`` is never placed: a book uploaded
        before positions were derived has none, and a chapter that cannot say
        where it begins cannot be said to hold anything. A position before every
        chapter's start -- front matter the table of contents does not name --
        likewise belongs to no chapter, and is answered ``None`` rather than
        attributed to the first.
        """
        holding: list[tuple[Position, Position, Chapter]] = []
        for chapter in chapters:
            start = chapter.start_position
            if start is None or start > position:
                continue
            end = chapter.end_position or _ENDLESS
            if end <= position:
                continue
            holding.append((start, end, chapter))

        if not holding:
            return None

        # Two stable sorts rather than one key, because the two halves of the rule
        # run opposite ways: widest end first, then latest start last, which leaves
        # the tightest end last within each group of chapters starting together.
        holding.sort(key=lambda held: held[1], reverse=True)
        holding.sort(key=lambda held: held[0])
        return holding[-1][2]
